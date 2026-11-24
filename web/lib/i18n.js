// Pure localisation helpers (no DOM, no ComfyUI imports).

export const LOCALES_ROUTE = "/charsheet/locales";

/** "zh*" locales (from Comfy.Locale, else the browser languages) use Chinese; everything else English. */
export function resolveLang(comfyLocale, navigatorLangs) {
  const isZh = (l) => typeof l === "string" && /^zh(\b|[-_])/i.test(l);
  if (typeof comfyLocale === "string" && comfyLocale) return isZh(comfyLocale) ? "zh" : "en";
  const langs = Array.isArray(navigatorLangs) ? navigatorLangs : [];
  return langs.some(isZh) ? "zh" : "en";
}

export function getByPath(obj, path) {
  return path.split(".").reduce((cur, k) => (cur && typeof cur === "object" ? cur[k] : undefined), obj);
}

export function interpolate(text, vars) {
  return text.replace(/\{\{(\w+)\}\}/g, (m, k) => (vars && k in vars ? String(vars[k]) : m));
}

/** `strings` is the nested UI strings object, `dataMap` maps canonical Chinese values to display text. */
export function createTranslator(strings, dataMap) {
  const data = dataMap && typeof dataMap === "object" ? dataMap : {};
  const t = (key, vars) => {
    const raw = getByPath(strings || {}, key);
    return typeof raw === "string" ? interpolate(raw, vars) : key;
  };
  const d = (value) => {
    if (typeof value !== "string") return value;
    const hit = data[value];
    return typeof hit === "string" && hit ? hit : value;
  };
  return { t, d };
}

/** Load {strings, data} from the backend; resolves to empty maps on any failure so keys still render. */
export async function loadLocale(lang, fetchFn = (url) => fetch(url)) {
  try {
    const resp = await fetchFn(`${LOCALES_ROUTE}/${lang}.json`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const body = await resp.json();
    return { strings: body.strings || {}, data: body.data || {} };
  } catch {
    return { strings: {}, data: {} };
  }
}
