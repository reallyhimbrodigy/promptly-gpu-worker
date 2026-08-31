import os, modal
app = modal.App("presign-freeze-out")
img = modal.Image.debian_slim().pip_install("boto3")
S=[modal.Secret.from_name("promptly-secrets")]
@app.function(image=img, secrets=S, timeout=300)
def go(jid: str):
    import boto3
    s3=boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    b=os.environ.get("S3_BUCKET_NAME") or "thisismybucketagainwooo"
    k=f"forensics/{jid}/output.mp4"
    try:
        s3.head_object(Bucket=b,Key=k)
    except Exception as e:
        return "MISSING:"+str(e)[:80]
    return s3.generate_presigned_url("get_object",Params={"Bucket":b,"Key":k},ExpiresIn=3600)
@app.local_entrypoint()
def main(jid: str = "579dcbe6-5ca5-4e6f-b2f2-3c70da557358"):
    print("URL="+go.remote(jid))
