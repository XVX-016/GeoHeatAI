import { createFileRoute } from "@tanstack/react-router";
import { BarChart2, FileImage, FileText, Map, type LucideIcon } from "lucide-react";

export const Route = createFileRoute("/app/export")({
  component: ExportPage,
});

function ExportPage() {
  const handleDownload = (name: string, size: string) => {
    const link = document.createElement("a");
    link.href = "#";
    link.download = name;
    link.dispatchEvent(new Event("click"));
    console.log(`Download triggered: ${name} (${size})`);
  };

  const handleGenerateReport = () => {
    console.log("Generating PDF report...");
    alert("Technical report generation initiated. This would trigger a server-side PDF render.");
  };

  return (
    <div className="px-8 py-8">
      <div>
        <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">EXPORT</div>
        <div className="mt-3 font-sans text-[22px] font-semibold text-white">
          Download results & methodology
        </div>
        <p className="mt-2 max-w-2xl font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
          Package raster maps, intervention geometry, model evidence, and reviewer-ready reports.
        </p>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <ExportCard
          Icon={FileImage}
          format="GEOTIFF"
          formatDescription="Georeferenced raster for GIS tools"
          title="Heat stress rasters"
          desc="Baseline and optimized 30m LST layers for Delhi NCR."
          action="DOWNLOAD · 284 MB"
          onClick={() => handleDownload("delhi-ncr-lst-rasters.tif", "284 MB")}
        />
        <ExportCard
          Icon={Map}
          format="GEOJSON"
          formatDescription="Vector intervention zones with attributes"
          title="Intervention layer"
          desc="Spatial plan with zone attributes, priority scores, and implementation metadata."
          action="DOWNLOAD · 18 MB"
          onClick={() => handleDownload("intervention-layer.geojson", "18 MB")}
        />
        <ExportCard
          Icon={BarChart2}
          format="CSV + PNG"
          formatDescription="Tabular SHAP values and chart images"
          title="SHAP analysis"
          desc="Global and local feature importance values explaining heat drivers."
          action="DOWNLOAD · 4 MB"
          onClick={() => handleDownload("shap-analysis.zip", "4 MB")}
        />
        <ExportCard
          Icon={FileText}
          format="PDF"
          formatDescription="Human-readable technical summary"
          title="Technical report"
          desc="Methodology, validation results, and full recommendation narrative."
          action="GENERATE REPORT"
          onClick={handleGenerateReport}
        />
      </div>

      <div className="mt-6 border border-[#1a1a1a] bg-[#0a0a0a] p-6">
        <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">MODEL PROVENANCE</div>
        <p className="mt-2 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
          Traceability metadata for the model, imagery, validation metrics, and spatial resolution.
        </p>
        <div className="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          <KV
            keyLabel="MODEL TYPE"
            valueText="XGBoost + U-Net PINN ensemble"
            description="Gradient boosting, segmentation, and physics-informed learning combined."
          />
          <KV
            keyLabel="TRAINING DATA"
            valueText="Landsat 8/9 2018-2023"
            description="Thermal satellite archive used for historical heat patterns."
          />
          <KV keyLabel="CITY" valueText="Delhi NCR" description="Primary analysis boundary." />
          <KV keyLabel="RESOLUTION" valueText="30m UTM" description="Thirty-meter projected grid." />
          <KV
            keyLabel="SCENES"
            valueText="847 cloud-masked"
            description="Satellite images filtered for usable observations."
          />
          <KV
            keyLabel="SPATIAL CV R²"
            valueText="0.87"
            description="Cross-validated model fit across held-out spatial regions."
          />
          <KV keyLabel="RMSE" valueText="1.34°C" description="Average temperature prediction error." />
          <KV
            keyLabel="PHYSICS LOSS"
            valueText="SEB (Rn=G+H+LE)"
            description="Surface Energy Balance constraint on heat exchange terms."
          />
        </div>
      </div>
    </div>
  );
}

function ExportCard({
  Icon,
  format,
  formatDescription,
  title,
  desc,
  action,
  onClick,
}: {
  Icon: LucideIcon;
  format: string;
  formatDescription: string;
  title: string;
  desc: string;
  action: string;
  onClick: () => void;
}) {
  return (
    <div className="border border-[#1a1a1a] p-6 transition-colors hover:border-[#1a1a1a]">
      <div className="flex items-start gap-3">
        <Icon className="mt-0.5 h-4 w-4 text-[#a0a0a0]" />
        <div>
          <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">{format}</div>
          <div className="mt-1 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
            {formatDescription}
          </div>
        </div>
      </div>
      <div className="mt-4 font-sans text-[15px] font-medium text-white">{title}</div>
      <div className="mt-2 font-sans text-[13px] leading-[1.7] text-[#a0a0a0]">{desc}</div>
      <button
        type="button"
        onClick={onClick}
        className="mt-5 w-full rounded-none border border-[#1a1a1a] px-4 py-2 font-mono text-[10px] uppercase text-white transition-colors hover:border-white hover:bg-white hover:text-black"
      >
        {action}
      </button>
    </div>
  );
}

function KV({
  keyLabel,
  valueText,
  description,
}: {
  keyLabel: string;
  valueText: string;
  description: string;
}) {
  return (
    <div>
      <div className="font-mono text-[9px] uppercase text-[#6b6b6b]">{keyLabel}</div>
      <div className="mt-2 font-mono text-[11px] text-white">{valueText}</div>
      <div className="mt-1 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">{description}</div>
    </div>
  );
}
