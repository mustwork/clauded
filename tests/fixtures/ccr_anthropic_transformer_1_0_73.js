  }
  return zf(n);
}
var Wt = b0;
var Vf = (r) => r <= 0 ? "none" : r <= 1024 ? "low" : r <= 8192 ? "medium" : "high";
var Kf = (r, e) => (r.includes("base64") && (r = r.split("base64").pop(), r.startsWith(",") && (r = r.slice(1))), `data:${e};base64,${r}`);
var bo = class {
  constructor(e) {
    this.options = e;
    this.useBearer = this.options?.UseBearer ?? false;
  }
  name = "Anthropic";
  endPoint = "/v1/messages";
  useBearer;
  logger;
  async auth(e, t) {
    let n = {};
    return this.useBearer ? (n.authorization = `Bearer ${t.apiKey}`, n["x-api-key"] = void 0) : (n["x-api-key"] = t.apiKey, n.authorization = void 0), { body: e, config: { headers: n } };
  }
  async transformRequestOut(e) {
    let t = [];
    if (e.system) {
      if (typeof e.system == "string") t.push({ role: "system", content: e.system });
      else if (Array.isArray(e.system) && e.system.length) {
        let i = e.system.filter((u) => u.type === "text" && u.text).map((u) => ({ type: "text", text: u.text, cache_control: u.cache_control }));
