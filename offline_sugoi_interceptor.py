import json
import fastapi
import httpx
import jinja2
import uvicorn
# 14367
# 14366

app = fastapi.FastAPI()

with open("config.json","r") as f:
    config:dict = json.load(f)

tabby = config["text_completion"]
api_key = config["api_key"]
model = config.get("model")
jinja = config.get("jinja","")
prompt:str = config.get("prompt","")
session = httpx.AsyncClient()

print("=== Config is as follows ===")
print("Endpoint:",tabby)
print("api_key:","Provided" if config["api_key"] else "N/A")
print("model:",f"Provided. {model}" if model else "Auto. Might not be enabled for some models.")
print("Chat completion (OAI Wrap):","Enabled" if jinja else "Disabled. jinja template not provided.")
print("Text Completion (SugoiTL):","Enabled" if prompt else "Disabled. prompt template not provided.")
if not jinja and not prompt:
    print("Either Chat or Text completion is not provided. Aborting...")
    raise SystemExit()
print("===  ===")

### Advanced Configuration ###


# Flag hints.
flags = "DIALOGUE"

sp_hint = {
    "NAMES": " Translate the name given in the input.",
    "DIALOGUE": " Translate the dialogue given in the input.",
    "":""
}

### Japanese Name Hints ###

hints = {
    "バルゴ":"[Bargo, Female/She]",
    "エリシア":"[Elysia, Female/She]"
}

### End Name Hints ###

print("Current flag:",flags,"\n",sp_hint[flags])

if flags == "NAMES":
    print("Using name cache...")
    dict_cache = {}
else:
    dict_cache = None

if jinja:
    jinja_template = jinja2.Template(jinja)
else:
    jinja_template = None
    
def execption_wrapper(*args):
    print(*args)
    
@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def chat_complete(r:fastapi.Request):
    if jinja_template is None:
        return 405
    c = await r.json()
    msgs = c.get("messages",[])
    bos_token = "<s>"
    eos_token = "</s>"
    print(msgs)
    prompt = jinja_template.render({"bos_token":bos_token,"eos_token":eos_token,"messages":msgs,"raise_exception":execption_wrapper})
    z = {
        "stream": False,
        "max_tokens": 300,
        "temperature": 0.6,
        "min_p": 0.1,
        "repetition_penalty": 1.05,
        "penalty_range": 4096,
        "model":model,
        "stop": ["\n###","###","\n\n","[/INST]"],
        "prompt": prompt,
    }
    # print(prompt)
    resp = await session.post(
        f"{tabby}/v1/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "user-agent": "SugoiInterceptor/1.0.0 (Via ChatCompletion)",
            # Ngrok
            "ngrok-skip-browser-warning": "True",
        },
        json=z,
        timeout=None,
    )
    print(prompt)
    print(msgs[-1])
    data = resp.json()
    
    responseline = data["choices"][0]["text"]
    # Rewrite for OAI spec. Hella stupid
    data["choices"][0]["message"] = {"content":responseline}
    print(data)
    return data, 200
    

@app.post("/")
async def main(r: fastapi.Request):
    c = await r.json()
    lines = []
    for line in c["content"]:
        fmt_line = line.replace("<br>","<|>")
        if line[0] == "「" and line[-1] == "」":
            fmt_line = list(fmt_line)
            fmt_line[0] = "\""
            fmt_line[-1] = "\""
            fmt_line = "".join(fmt_line)
        if line[0] == "（" and line[-1] == "）":
            fmt_line = list(fmt_line)
            fmt_line[0] = "("
            fmt_line[-1] = ")"
            fmt_line = "".join(fmt_line)
        fmt_line = fmt_line.replace("【"," [").replace("】","] ").strip()
        k_note = sp_hint[flags]
        if flags == "NAMES" and dict_cache:
            if fmt_line in dict_cache:
                lines.append(dict_cache[fmt_line])
                continue
        encapsulate = True if fmt_line[0] not in ['"',"'","[","]"] else False
        if encapsulate:
            fmt_line = f"`{fmt_line}`"
        fmt_prompt = prompt.format(fmt_line=fmt_line)
        if encapsulate:
            fmt_prompt += "`"
        print(fmt_prompt)
        z = {
            "stream": False,
            "max_tokens": 300,
            "temperature": 0.6,
            "min_p": 0.1,
            "repetition_penalty": 1.05,
            "penalty_range": 4096,
            "stop": ["\n###","###","\n\n"],
            "prompt": prompt,
        }
        resp = await session.post(
            f"{tabby}/v1/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "user-agent": "SugoiInterceptor/1.0.0",
                # Ngrok
                "ngrok-skip-browser-warning": "True",
            },
            json=z,
            timeout=None,
        )
        # print(resp.json())
        responseline = resp.json()["choices"][0]["text"].replace("<|>","<br>")
        if encapsulate and responseline[-1] == "`":
            responseline = responseline.rstrip("`")
        lines.append(responseline)
        print(f"Orig: {line}\nMTL:{responseline}")
        if flags == "NAMES" and dict_cache:
            if fmt_line not in dict_cache:
                dict_cache[fmt_line] = responseline
                continue
    return fastapi.responses.JSONResponse(lines)


uvicorn.run(app, port=14366)
