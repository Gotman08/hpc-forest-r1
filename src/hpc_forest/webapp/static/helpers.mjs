export const escapeHTML = value => String(value ?? "").replace(/[&<>"']/g, c =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
export const finite = n => typeof n === "number" && Number.isFinite(n);
export function seconds(n) {
  if (!finite(n) || n < 0) return "—";
  const [scale, unit] = n < .001 ? [1e6, "µs"] : n < 1 ? [1e3, "ms"] : [1, "s"];
  return new Intl.NumberFormat("fr-FR", {maximumFractionDigits:3}).format(n * scale) + " " + unit;
}
export function speedup(n) {
  return finite(n) && n > 0 ? new Intl.NumberFormat("fr-FR", {maximumFractionDigits:3}).format(n) + " ×" : "—";
}
export function size(n) {
  if (!finite(n)) return "—";
  if (n < 1024) return n + " o";
  if (n < 1024 * 1024) return (n / 1024).toFixed(1).replace(".", ",") + " Kio";
  return (n / 1024 / 1024).toFixed(1).replace(".", ",") + " Mio";
}
export function date(n) {
  return finite(n) ? new Intl.DateTimeFormat("fr-FR", {dateStyle:"medium",timeStyle:"short"}).format(n*1000) : "—";
}
export const states = {
  staging:["Transfert","blue"], planned:["Plan prêt","blue"], submitting:["Soumission","blue"],
  queued:["En file ROMEO","amber"], validating:["Vérification initiale","blue"], preparing:["Préparation distante","blue"],
  collecting:["Récupération des résultats","blue"], cancelled:["Annulée","gray"],
  confirmed:["Gain confirmé","green"], no_gain:["Aucun gain confirmé","gray"],
  unconfirmed:["Résultat non confirmé","amber"], running:["Recherche en cours","blue"],
  confirming:["Confirmation","blue"], initialized:["Initialisée","blue"],
  checkpointed:["Point de reprise","amber"], failed:["Interrompue","red"],
  recovery_required:["Réconciliation requise","amber"],
  unavailable:["Preuves indisponibles","red"], needs_input:["À compléter","amber"],
  ready:["Contrat prêt","green"], prepared:["Prête à transférer","blue"],
  valid:["Correct","green"], incorrect:["Incorrect","red"],
  infrastructure_error:["Erreur d’infrastructure","amber"], pending:["En attente","gray"],
  completed:["Terminée","green"], generating:["Génération","blue"],
};
export const stateName = state => states[state]?.[0] || String(state || "Non renseigné").replaceAll("_"," ");
export function badge(state, label) {
  return '<span class="badge ' + (states[state]?.[1] || "gray") + '"><i></i>' +
    escapeHTML(label ?? stateName(state)) + '</span>';
}
export const short = value => String(value ?? "").slice(0,10);
export function routeFor(record) {
  const id = encodeURIComponent(record.id);
  if (record.kind === "project") return "#/prepare/" + id;
  if (record.kind === "mission") return "#/mission/run/" + id;
  if (record.kind === "prepared") return "#/mission/prepared/" + id;
  return "#/mission/campaign/" + id;
}
export async function api(path, options = {}) {
  const response = await fetch("/api" + path, {
    ...options,
    headers: {"X-Forest-Request":"1", ...(options.body instanceof FormData ? {} :
      options.body ? {"Content-Type":"application/json"} : {}), ...options.headers},
  });
  let payload;
  try { payload = await response.json(); }
  catch { throw new Error("Le serveur n’a pas renvoyé une réponse lisible."); }
  if (!response.ok) throw new Error(payload.error || payload.detail || "L’action n’a pas abouti.");
  return payload;
}
export function safeJSON(value) { return escapeHTML(JSON.stringify(value, null, 2)); }
