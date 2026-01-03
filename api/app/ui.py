from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
def home():
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>SaffronQueue UI</title>
  <style>
    body{font-family: sans-serif; max-width: 900px; margin: 30px auto; padding: 0 12px;}
    input,button{padding:10px; font-size:16px;}
    a{color: #0b5fff; text-decoration: none;}
    a:hover{text-decoration: underline;}
    #jobs{margin-top:20px;}
    .job{border:1px solid #ddd; padding:12px; border-radius:10px; margin:10px 0;}
    .row{display:flex; gap:10px;}
    .grow{flex:1;}
    pre{white-space:pre-wrap; word-break:break-word;}
    .actions{margin-top:6px; display:flex; gap:10px; align-items:center; flex-wrap: wrap;}
    .muted{color:#666;}
    .badge{font-weight:700;}
  </style>
</head>
<body>
  <h2>SaffronQueue</h2>

  <div class="row">
    <input id="payload" class="grow" placeholder="payload مثلا: convert file X / build report / ..." />
    <button onclick="submitJob()">Submit Job</button>
  </div>

  <div style="margin-top:10px;">
    <label>Max Attempts:</label>
    <input id="max_attempts" type="number" value="5" min="1" max="20" style="width:90px;">
  </div>

  <div id="jobs"></div>

<script>
let jobIds = [];

async function submitJob(){
  const payload = document.getElementById('payload').value.trim();
  const maxAttempts = parseInt(document.getElementById('max_attempts').value || "5", 10);
  if(!payload){ alert("payload خالیه"); return; }

  const res = await fetch('/jobs', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({payload: payload, max_attempts: maxAttempts})
  });

  const data = await res.json();
  if(!res.ok){
    alert("خطا: " + (data?.detail || res.status));
    return;
  }

  jobIds.unshift(data.id);
  document.getElementById('payload').value = "";
  await render(); // فوری آپدیت بعد از submit
}

async function fetchJob(id){
  const res = await fetch('/jobs/' + id);
  if(!res.ok) throw new Error("fetch failed");
  return await res.json();
}

async function copyHash(h){
  try {
    await navigator.clipboard.writeText(h);
    alert("Hash copied!");
  } catch(e) {
    alert("Copy failed");
  }
}

function badgeFor(j){
  const done = (j.status === "succeeded" && j.result);
  if(done) return {text:"✅ hashed", cls:"badge"};
  if(j.status === "failed") return {text:"❌ failed", cls:"badge"};
  return {text:"⏳ processing", cls:"badge"};
}

async function render(){
  const jobsDiv = document.getElementById('jobs');
  jobsDiv.innerHTML = "<h3>Jobs</h3>";

  if(jobIds.length === 0){
    const empty = document.createElement('div');
    empty.className = 'muted';
    empty.innerText = "هنوز هیچ جابی ثبت نشده. یکی بساز 🙂";
    jobsDiv.appendChild(empty);
    return;
  }

  for(const id of jobIds.slice(0, 20)){
    try{
      const j = await fetchJob(id);
      const el = document.createElement('div');
      el.className = 'job';

      const done = (j.status === "succeeded" && j.result);
      const b = badgeFor(j);

      const actions = done ? `
        <div class="actions">
          <button onclick="copyHash('${j.result}')">Copy hash</button>
          <a href="/jobs/${j.id}/checksum">Download .sha256</a>
        </div>
      ` : "";

      el.innerHTML = `
        <b>${j.id}</b><br/>
        status: <b>${j.status}</b> <span class="${b.cls}">(${b.text})</span>
        | attempts: ${j.attempts}/${j.max_attempts}<br/>
        ${actions}
        <details style="margin-top:8px;">
          <summary>payload/result</summary>
          <pre>payload: ${j.payload}
result: ${j.result || ""}
last_error: ${j.last_error || ""}</pre>
        </details>
      `;

      jobsDiv.appendChild(el);
    }catch(e){
      // اگر یکی از jobها حذف/خطا شد، بیخیال
    }
  }
}

// هر 5 ثانیه رفرش
setInterval(render, 5000);
// یکبار هم اول صفحه
render();
</script>
</body>
</html>
"""
