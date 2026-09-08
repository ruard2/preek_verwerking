/* AfterSermon — volledige taalkeuzelijst voor de uitvoer-taal instelling.
   Bevat alle talen waarvoor hedendaagse LLM's (GPT-5 e.d.) betrouwbaar tekst
   kunnen produceren. ISO 639-1/3 codes. */

window.TALEN = [
  { code: "",   label: "Zelfde als de preek (aanbevolen)" },
  // ── Europees ──────────────────────────────────────────────────────────────
  { code: "nl", label: "Nederlands" },
  { code: "af", label: "Afrikaans" },
  { code: "en", label: "English" },
  { code: "de", label: "Deutsch" },
  { code: "fr", label: "Français" },
  { code: "es", label: "Español" },
  { code: "pt", label: "Português" },
  { code: "it", label: "Italiano" },
  { code: "ro", label: "Română" },
  { code: "pl", label: "Polski" },
  { code: "cs", label: "Čeština" },
  { code: "sk", label: "Slovenčina" },
  { code: "hu", label: "Magyar" },
  { code: "hr", label: "Hrvatski" },
  { code: "sl", label: "Slovenščina" },
  { code: "sr", label: "Srpski" },
  { code: "bg", label: "Български" },
  { code: "uk", label: "Українська" },
  { code: "ru", label: "Русский" },
  { code: "be", label: "Беларуская" },
  { code: "lt", label: "Lietuvių" },
  { code: "lv", label: "Latviešu" },
  { code: "et", label: "Eesti" },
  { code: "fi", label: "Suomi" },
  { code: "sv", label: "Svenska" },
  { code: "no", label: "Norsk" },
  { code: "da", label: "Dansk" },
  { code: "is", label: "Íslenska" },
  { code: "fy", label: "Frysk" },
  { code: "cy", label: "Cymraeg" },
  { code: "ga", label: "Gaeilge" },
  { code: "eu", label: "Euskara" },
  { code: "ca", label: "Català" },
  { code: "gl", label: "Galego" },
  { code: "sq", label: "Shqip" },
  { code: "mk", label: "Македонски" },
  { code: "el", label: "Ελληνικά" },
  { code: "tr", label: "Türkçe" },
  // ── Midden-Oosten & Centraal-Azië ─────────────────────────────────────────
  { code: "ar", label: "العربية" },
  { code: "he", label: "עברית" },
  { code: "fa", label: "فارسی" },
  { code: "ur", label: "اردو" },
  { code: "az", label: "Azərbaycan" },
  { code: "kk", label: "Қазақша" },
  { code: "uz", label: "O'zbek" },
  { code: "ky", label: "Кыргызча" },
  { code: "tg", label: "Тоҷикӣ" },
  { code: "tk", label: "Türkmen" },
  // ── Zuid-Azië ─────────────────────────────────────────────────────────────
  { code: "hi", label: "हिन्दी" },
  { code: "bn", label: "বাংলা" },
  { code: "pa", label: "ਪੰਜਾਬੀ" },
  { code: "gu", label: "ગુજરાતી" },
  { code: "mr", label: "मराठी" },
  { code: "ta", label: "தமிழ்" },
  { code: "te", label: "తెలుగు" },
  { code: "kn", label: "ಕನ್ನಡ" },
  { code: "ml", label: "മലയാളം" },
  { code: "si", label: "සිංහල" },
  { code: "ne", label: "नेपाली" },
  // ── Oost- & Zuidoost-Azië ─────────────────────────────────────────────────
  { code: "zh", label: "中文（简体）" },
  { code: "zh-tw", label: "中文（繁體）" },
  { code: "ja", label: "日本語" },
  { code: "ko", label: "한국어" },
  { code: "vi", label: "Tiếng Việt" },
  { code: "th", label: "ภาษาไทย" },
  { code: "id", label: "Bahasa Indonesia" },
  { code: "ms", label: "Bahasa Melayu" },
  { code: "tl", label: "Filipino" },
  { code: "lo", label: "ລາວ" },
  { code: "km", label: "ខ្មែរ" },
  { code: "my", label: "မြန်မာ" },
  // ── Afrika ────────────────────────────────────────────────────────────────
  { code: "sw", label: "Kiswahili" },
  { code: "am", label: "አማርኛ" },
  { code: "so", label: "Soomaali" },
  { code: "ha", label: "Hausa" },
  { code: "yo", label: "Yorùbá" },
  { code: "ig", label: "Igbo" },
  { code: "zu", label: "isiZulu" },
  { code: "xh", label: "isiXhosa" },
  { code: "st", label: "Sesotho" },
  { code: "sn", label: "chiShona" },
  { code: "mg", label: "Malagasy" },
  { code: "rw", label: "Kinyarwanda" },
  { code: "lg", label: "Luganda" },
  { code: "ln", label: "Lingála" },
  { code: "wo", label: "Wolof" },
  { code: "ff", label: "Fula" },
  // ── Amerika ───────────────────────────────────────────────────────────────
  { code: "qu", label: "Quechua" },
  { code: "gn", label: "Guaraní" },
  { code: "ht", label: "Kreyòl ayisyen" },
];

/**
 * Bouw een <select>-element met alle talen.
 * @param {string} id       - id-attribuut van het <select>
 * @param {string} waarde   - initieel geselecteerde ISO-code
 * @param {boolean} metAuto - voeg "Zelfde als preek" optie toe (voor kerkkant)
 */
window.maakTaalSelect = function(id, waarde, metAuto = true) {
  const sel = document.createElement('select');
  sel.id = id;
  TALEN.forEach(t => {
    if (!metAuto && t.code === '') return;
    const opt = document.createElement('option');
    opt.value = t.code;
    opt.textContent = t.label;
    if (t.code === (waarde || '')) opt.selected = true;
    sel.appendChild(opt);
  });
  return sel;
};
