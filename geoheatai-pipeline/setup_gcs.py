"""
GeoHeatAI — One-time setup script to create GCS bucket and grant permissions.
"""

import sys
from pathlib import Path
from google.cloud import storage

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config.config import GCS_BUCKET

def main():
    project_id = "geoheatai"
    location = "asia-south1" # Mumbai (closest region to Delhi NCR for GEE latency)
    
    print(f"Connecting to Google Cloud Storage client for project '{project_id}'...")
    try:
        client = storage.Client(project=project_id)
    except Exception as e:
        print(f"Error creating GCS client: {e}")
        print("Please ensure you are authenticated by running:")
        print("  gcloud auth application-default login")
        sys.exit(1)
        
    # Check if bucket exists, create it if not
    try:
        bucket = client.get_bucket(GCS_BUCKET)
        print(f"✓ Bucket '{GCS_BUCKET}' already exists, skipping creation.")
    except Exception:
        print(f"Creating bucket '{GCS_BUCKET}' in region '{location}'...")
        try:
            bucket = client.create_bucket(GCS_BUCKET, location=location)
            print(f"✓ Bucket '{GCS_BUCKET}' created successfully.")
        except Exception as e:
            print(f"Error creating bucket: {e}")
            sys.exit(1)
            
    # Grant permissions
    print("Updating bucket IAM policy bindings...")
    try:
        policy = bucket.get_iam_policy(requested_policy_version=3)
        
        # 1. Grant GEE Service Account write permission
        gee_sa = "serviceAccount:geoheatai@geoheatai.iam.gserviceaccount.com"
        creator_members = policy.get("roles/storage.objectCreator", set())
        creator_members.add(gee_sa)
        policy["roles/storage.objectCreator"] = creator_members
        print(f"  Added GEE service account write access (objectCreator).")

        # 2. Grant Personal Account read permission for download poller
        personal_user = "user:tanmmay2005@gmail.com"
        viewer_members = policy.get("roles/storage.objectViewer", set())
        viewer_members.add(personal_user)
        policy["roles/storage.objectViewer"] = viewer_members
        print(f"  Added user tanmmay2005@gmail.com read access (objectViewer).")
        
        bucket.set_iam_policy(policy)
        print("✓ IAM policy updated successfully.")
    except Exception as e:
        print(f"Error setting IAM permissions: {e}")
        print("Make sure you have Owner/Storage Admin access in the GCP Project console.")

    print("\n✓ GCS bucket ready. Now run:")
    print("  python src/ingestion/run_pipeline.py --resubmit-failed")
    print("to resubmit export tasks to GCS.")

if __name__ == "__main__":
    main()
