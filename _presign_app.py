import os, modal
app = modal.App("agentic-presign")
img = modal.Image.debian_slim().pip_install("boto3")
@app.function(image=img, secrets=[modal.Secret.from_name("promptly-secrets")], timeout=300)
def go(k: str):
    import boto3
    s3=boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    b=os.environ.get("S3_BUCKET_NAME") or "thisismybucketagainwooo"
    return s3.generate_presigned_url("get_object",Params={"Bucket":b,"Key":k},ExpiresIn=604800)
@app.local_entrypoint()
def main(key: str = ""):
    print("URL="+go.remote(key))
