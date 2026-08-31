import os, modal
app = modal.App("presign-freeze-src")
img = modal.Image.debian_slim().pip_install("boto3")
S=[modal.Secret.from_name("promptly-secrets")]
@app.function(image=img, secrets=S, timeout=300)
def go():
    import boto3
    s3=boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    b=os.environ.get("S3_BUCKET_NAME") or "thisismybucketagainwooo"
    return s3.generate_presigned_url("get_object",
        Params={"Bucket":b,"Key":"ab-sources/talking-head-v1/625dfdc5-73s.mp4"},
        ExpiresIn=3600)
@app.local_entrypoint()
def main():
    print("URL="+go.remote())
