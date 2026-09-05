from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
API_MODULE = (ROOT / "frontend2" / "api.js").as_uri()


def test_frontend_json_client_distinguishes_http_network_and_contract_errors() -> None:
    script = f"""
const {{requestJSON, ApiError}} = await import({API_MODULE!r} + "?runtime-test=1");

globalThis.fetch = async () => new Response('{{"status":"ok","items":[]}}', {{status: 200}});
const empty = await requestJSON("/asociaciones-sensores?localidad=colchane");
if (!Array.isArray(empty.items) || empty.items.length !== 0) throw new Error("200 vacío inválido");

for (const status of [404, 500, 502, 503, 504]) {{
  globalThis.fetch = async () => new Response(JSON.stringify({{detail: "fallo controlado"}}), {{status}});
  try {{
    await requestJSON("/asociaciones-sensores?localidad=colchane");
    throw new Error("se esperaba ApiError " + status);
  }} catch (error) {{
    if (!(error instanceof ApiError) || error.status !== status || error.message !== "fallo controlado") throw error;
  }}
}}

globalThis.fetch = async () => new Response("respuesta no JSON", {{status: 200}});
try {{
  await requestJSON("/asociaciones-sensores?localidad=colchane");
  throw new Error("se esperaba error JSON");
}} catch (error) {{
  if (!(error instanceof ApiError) || !error.message.includes("JSON inválida")) throw error;
}}

globalThis.fetch = async () => {{ throw new TypeError("fetch failed"); }};
try {{
  await requestJSON("/asociaciones-sensores?localidad=colchane");
  throw new Error("se esperaba error de red");
}} catch (error) {{
  if (!(error instanceof ApiError) || error.status !== 0 || !error.message.includes("conectar con FastAPI")) throw error;
}}
"""
    subprocess.run(
        [
            "node",
            "--experimental-default-type=module",
            "--input-type=module",
            "--eval",
            script,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
