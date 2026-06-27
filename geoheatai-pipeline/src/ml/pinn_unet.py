"""
GeoHeatAI — Physics-Informed U-Net for LST prediction.

A PyTorch spatial prediction model that estimates Land Surface Temperature
(LST_C) from a 14-band (or 18-band) feature stack. Applies a custom physical
loss term representing the surface energy balance (Bowen ratio proxy constraint).
"""

import os
import sys
import json
from pathlib import Path
import h5py
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import r2_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.config import DATA_PROCESSED

# --- 1. PyTorch Dataset ---
class DelhiTilesDataset(Dataset):
    """Custom PyTorch dataset to read patches from HDF5."""
    def __init__(self, h5_path: Path):
        self.h5_path = h5_path
        with h5py.File(self.h5_path, "r") as h5f:
            self.length = h5f["patches/features"].shape[0]
            self.band_names = [n.decode("utf-8") for n in h5f["metadata/band_names"][:]]
        
        # Locate indices for physics loss
        try:
            self.ndvi_idx = self.band_names.index("NDVI")
        except ValueError:
            self.ndvi_idx = 11  # fallback default
            
        try:
            self.ndbi_idx = self.band_names.index("NDBI")
        except ValueError:
            self.ndbi_idx = 12  # fallback default

    def __len__(self):
        return self.length

    def __getitem__(self, idx):
        # We read directly from HDF5 file
        with h5py.File(self.h5_path, "r") as h5f:
            # Transpose to PyTorch shape: (Channels, Height, Width)
            feature = h5f["patches/features"][idx].transpose(2, 0, 1)
            label = h5f["patches/labels"][idx].transpose(2, 0, 1)
        return torch.tensor(feature, dtype=torch.float32), torch.tensor(label, dtype=torch.float32)

# --- 2. U-Net Architecture ---
class DoubleConv(nn.Module):
    """(Conv2d -> BatchNorm2d -> ReLU) * 2"""
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.double_conv = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True)
        )

    def forward(self, x):
        return self.double_conv(x)

class DownBlock(nn.Module):
    """DoubleConv then MaxPool"""
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.conv = DoubleConv(in_channels, out_channels)
        self.pool = nn.MaxPool2d(kernel_size=2, stride=2)

    def forward(self, x):
        conv_out = self.conv(x)
        pooled_out = self.pool(conv_out)
        return conv_out, pooled_out

class UpBlock(nn.Module):
    """Upsample, concatenate skip connection, and DoubleConv"""
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.up = nn.ConvTranspose2d(in_channels, in_channels // 2, kernel_size=2, stride=2)
        self.conv = DoubleConv(in_channels, out_channels)

    def forward(self, x, skip):
        x = self.up(x)
        # Pad if sizes don't match (due to rounding in pooling)
        diff_y = skip.size()[2] - x.size()[2]
        diff_x = skip.size()[3] - x.size()[3]
        x = F.pad(x, [diff_x // 2, diff_x - diff_x // 2, diff_y // 2, diff_y - diff_y // 2])
        
        # Concatenate along channel dimension
        x = torch.cat([skip, x], dim=1)
        return self.conv(x)

class UNet(nn.Module):
    """
    Standard U-Net with 4 encoder and 4 decoder blocks.
    Channels: in_channels -> 64 -> 128 -> 256 -> 512 -> 1024 -> decoders -> 1
    """
    def __init__(self, in_channels: int = 14):
        super().__init__()
        # Encoder
        self.down1 = DownBlock(in_channels, 64)
        self.down2 = DownBlock(64, 128)
        self.down3 = DownBlock(128, 256)
        self.down4 = DownBlock(256, 512)
        
        # Bottleneck
        self.bottleneck = DoubleConv(512, 1024)
        
        # Decoder
        self.up1 = UpBlock(1024, 512)
        self.up2 = UpBlock(512, 256)
        self.up3 = UpBlock(256, 128)
        self.up4 = UpBlock(128, 64)
        
        # Final output layer
        self.final_conv = nn.Conv2d(64, 1, kernel_size=1)

    def forward(self, x):
        s1, p1 = self.down1(x)
        s2, p2 = self.down2(p1)
        s3, p3 = self.down3(p2)
        s4, p4 = self.down4(p3)
        
        b = self.bottleneck(p4)
        
        d1 = self.up1(b, s4)
        d2 = self.up2(d1, s3)
        d3 = self.up3(d2, s2)
        d4 = self.up4(d3, s1)
        
        out = self.final_conv(d4)
        return out

# --- 3. Physics Loss (Surface Energy Balance) ---
class SurfaceEnergyBalanceLoss(nn.Module):
    """
    PINN loss: Standard MSE + lambda_physics * SEB_penalty
    Penalizes deviations violating Bowen Ratio B = H/(H+LE) constraints:
    - Vegetated pixels (NDVI > 0.3): B < 0.6
    - Built-up pixels (NDBI > 0.0): B > 0.4
    """
    def __init__(self, lambda_physics: float = 0.1, ndvi_idx: int = 11, ndbi_idx: int = 12):
        super().__init__()
        self.lambda_physics = lambda_physics
        self.ndvi_idx = ndvi_idx
        self.ndbi_idx = ndbi_idx
        self.mse = nn.MSELoss()

    def forward(self, pred: torch.Tensor, target: torch.Tensor, features: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        # Standard data loss
        mse_loss = self.mse(pred, target)
        
        # Extract physical bands from normalized features
        # Features shape: (batch, channels, 256, 256)
        ndvi = features[:, self.ndvi_idx:self.ndvi_idx+1, :, :]
        ndbi = features[:, self.ndbi_idx:self.ndbi_idx+1, :, :]

        # Physics Proxy Definitions
        # Sensible heat H is proportional to temperature deviation from spatial mean
        mean_lst = pred.mean(dim=(2, 3), keepdim=True)
        H = torch.abs(pred - mean_lst)
        
        # Latent heat LE is inversely proportional to (1 - NDVI)
        # Higher NDVI -> larger latent heat (evapotranspiration)
        LE = 1.0 / (1.0 - ndvi + 1e-5)
        
        # Bowen Ratio B = H / (H + LE)
        B = H / (H + LE + 1e-6)

        # 1. Vegetated pixels constraint: B < 0.6
        veg_mask = ndvi > 0.3
        penalty_veg = torch.tensor(0.0, device=pred.device)
        if veg_mask.any():
            violated_veg = F.relu(B - 0.6)
            penalty_veg = violated_veg[veg_mask].mean()

        # 2. Built-up pixels constraint: B > 0.4
        built_mask = ndbi > 0.0
        penalty_built = torch.tensor(0.0, device=pred.device)
        if built_mask.any():
            violated_built = F.relu(0.4 - B)
            penalty_built = violated_built[built_mask].mean()

        seb_penalty = penalty_veg + penalty_built
        total_loss = mse_loss + self.lambda_physics * seb_penalty
        
        return total_loss, mse_loss, seb_penalty

# --- 4. Training Loop ---
def train_pinn_unet(
    h5_path: Path,
    epochs: int = 50,
    batch_size: int = 4,
    lr: float = 1e-4,
    weight_decay: float = 1e-5,
    lambda_physics: float = 0.1
):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # Prepare datasets and loaders
    dataset = DelhiTilesDataset(h5_path)
    
    # 80/20 train/val random split by index
    n_samples = len(dataset)
    indices = list(range(n_samples))
    split = int(np.floor(0.2 * n_samples))
    
    np.random.seed(42)
    np.random.shuffle(indices)
    
    train_indices, val_indices = indices[split:], indices[:split]
    
    train_sampler = torch.utils.data.SubsetRandomSampler(train_indices)
    val_sampler = torch.utils.data.SubsetRandomSampler(val_indices)

    train_loader = DataLoader(dataset, batch_size=batch_size, sampler=train_sampler, pin_memory=True)
    val_loader = DataLoader(dataset, batch_size=batch_size, sampler=val_sampler, pin_memory=True)

    # Determine input features dimension
    with h5py.File(h5_path, "r") as h5f:
        in_channels = h5f["patches/features"].shape[3]
    
    print(f"Dataset has {in_channels} input features.")
    
    # Instantiate models
    model = UNet(in_channels=in_channels).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    
    criterion = SurfaceEnergyBalanceLoss(
        lambda_physics=lambda_physics,
        ndvi_idx=dataset.ndvi_idx,
        ndbi_idx=dataset.ndbi_idx
    )

    # AMP scaler for mixed precision
    scaler = torch.cuda.amp.GradScaler(enabled=(device.type == "cuda"))

    best_val_loss = float("inf")
    
    print("Starting training loop...")
    for epoch in range(1, epochs + 1):
        model.train()
        train_total_loss = 0.0
        train_mse_loss = 0.0
        train_physics_loss = 0.0

        for feats, targets in train_loader:
            feats, targets = feats.to(device), targets.to(device)
            
            optimizer.zero_grad()
            
            # Forward pass with mixed precision
            with torch.cuda.amp.autocast(enabled=(device.type == "cuda")):
                outputs = model(feats)
                loss, mse_l, phys_l = criterion(outputs, targets, feats)

            # Backward pass
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

            train_total_loss += loss.item() * feats.size(0)
            train_mse_loss += mse_l.item() * feats.size(0)
            train_physics_loss += phys_l.item() * feats.size(0)

        scheduler.step()

        # Validation
        model.eval()
        val_total_loss = 0.0
        val_mse_loss = 0.0
        
        all_preds = []
        all_targets = []

        with torch.no_grad():
            for feats, targets in val_loader:
                feats, targets = feats.to(device), targets.to(device)
                
                with torch.cuda.amp.autocast(enabled=(device.type == "cuda")):
                    outputs = model(feats)
                    loss, mse_l, _ = criterion(outputs, targets, feats)

                val_total_loss += loss.item() * feats.size(0)
                val_mse_loss += mse_l.item() * feats.size(0)
                
                # Save predictions for validation R²
                all_preds.extend(outputs.cpu().numpy().flatten())
                all_targets.extend(targets.cpu().numpy().flatten())

        # Average losses
        n_train = len(train_indices)
        n_val = len(val_indices)
        
        train_loss = train_total_loss / n_train
        train_mse = train_mse_loss / n_train
        train_phys = train_physics_loss / n_train
        val_loss = val_total_loss / n_val
        val_mse = val_mse_loss / n_val

        # Compute R² and RMSE
        val_r2 = r2_score(all_targets, all_preds)
        val_rmse = np.sqrt(val_mse)

        if epoch == 1 or epoch % 5 == 0:
            print(f"Epoch {epoch:02d}/{epochs:02d} | "
                  f"Train Loss: {train_loss:.4f} (MSE: {train_mse:.4f}, Phys: {train_phys:.4f}) | "
                  f"Val Loss: {val_loss:.4f} (MSE: {val_mse:.4f}) | "
                  f"Val R²: {val_r2:.4f} | Val RMSE: {val_rmse:.4f}°C")

        # Save checkpoint if best
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), DATA_PROCESSED / "pinn_unet_best.pt")

    print("\nTraining completed.")
    print(f"Best Validation Loss: {best_val_loss:.4f}")

    # Load best weights
    model.load_state_dict(torch.load(DATA_PROCESSED / "pinn_unet_best.pt"))
    model.eval()

    # Export to TorchScript via tracing
    print("Exporting model to TorchScript...")
    example_input = torch.randn(1, in_channels, 256, 256).to(device)
    
    # We trace the model to be compatible with multi-platform FastAPI server
    try:
        traced_model = torch.jit.trace(model, example_input)
        script_path = DATA_PROCESSED / "pinn_unet.torchscript"
        traced_model.save(str(script_path))
        print(f"Saved TorchScript model to {script_path}")
    except Exception as e:
        print(f"WARNING: TorchScript tracing failed: {e}. Attempting Script compilation...")
        try:
            # Fall back to scripting
            scripted_model = torch.jit.script(model)
            script_path = DATA_PROCESSED / "pinn_unet.torchscript"
            scripted_model.save(str(script_path))
            print(f"Saved scripted TorchScript model to {script_path}")
        except Exception as e_script:
            print(f"ERROR: Scripting also failed: {e_script}")

    return val_r2, val_rmse

def main():
    h5_path = DATA_PROCESSED / "delhi_tiles.h5"
    if not h5_path.exists():
        print(f"ERROR: HDF5 dataset not found at {h5_path}.")
        print("Please run src/preprocessing/tile_to_hdf5.py first.")
        sys.exit(1)

    r2, rmse = train_pinn_unet(h5_path, epochs=50, batch_size=4)
    print(f"\nFinal Validation metrics (PINN U-Net):")
    print(f"  R²   = {r2:.4f}")
    print(f"  RMSE = {rmse:.4f}°C")

    # Save Metrics for Pipeline Runner
    pinn_metrics = {
        "val_r2": float(r2),
        "val_rmse": float(rmse)
    }
    metrics_path = DATA_PROCESSED / "pinn_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(pinn_metrics, f, indent=2)
    print(f"Saved PINN metrics to {metrics_path}")

    return pinn_metrics

if __name__ == "__main__":
    main()
