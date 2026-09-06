import os, modal
app = modal.App("agentic-keycheck")
img = modal.Image.debian_slim()
@app.function(image=img, secrets=[modal.Secret.from_name("promptly-secrets")], timeout=120)
def go():
    return {k: (bool(os.environ.get(k)), len(os.environ.get(k) or ""))
            for k in ("ANTHROPIC_API_KEY","DEEPGRAM_API_KEY","AWS_ACCESS_KEY_ID",
                      "S3_BUCKET_NAME","CLAUDE_API_KEY")}
@app.local_entrypoint()
def main():
    for k,(present,n) in go.remote().items():
        print(f"  {'✅' if present else '❌'} {k:<22} {'present, '+str(n)+' chars' if present else 'ABSENT'}")
