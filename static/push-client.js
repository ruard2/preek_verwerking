/* Web-push aanzetten vanuit de browser: service worker registreren, toestemming
   vragen, abonneren, opslaan bij de server en meteen een testmelding sturen. */
window.AfterSermonPush = (() => {
  const T = s => (window.AfterSermonI18n ? AfterSermonI18n.text(s) : s);

  const ondersteund = () =>
    'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  const isIOS = () => /iP(hone|ad|od)/.test(navigator.userAgent);
  const geinstalleerd = () =>
    window.navigator.standalone === true ||
    (window.matchMedia && matchMedia('(display-mode: standalone)').matches);
  const iOSnietGeinstalleerd = () => isIOS() && !geinstalleerd();

  function b64urlNaarUint8(b64) {
    const pad = '='.repeat((4 - (b64.length % 4)) % 4);
    const s = (b64 + pad).replace(/-/g, '+').replace(/_/g, '/');
    const raw = atob(s);
    const arr = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
    return arr;
  }

  async function aanzetten(token, status) {
    status = status || (() => {});
    if (!ondersteund()) {
      status('fout', T('Dit apparaat of deze browser ondersteunt geen meldingen.'));
      return false;
    }
    try {
      const pk = await fetch('/api/push/publickey').then(r => r.json());
      if (!pk.beschikbaar || !pk.key) {
        status('fout', T('Meldingen zijn nog niet beschikbaar.'));
        return false;
      }
      const reg = await navigator.serviceWorker.register('/static/sw.js');
      const perm = await Notification.requestPermission();
      if (perm !== 'granted') {
        status('fout', T('Je hebt meldingen niet toegestaan.'));
        return false;
      }
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: b64urlNaarUint8(pk.key),
      });
      const r = await fetch('/api/push/abonneer', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({token, abonnement: sub}),
      });
      if (!r.ok) throw new Error();
      await fetch('/api/push/test', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({token}),
      });
      status('ok', T('Meldingen staan aan — je hebt een testmelding ontvangen.'));
      return true;
    } catch (e) {
      status('fout', T('Meldingen aanzetten is mislukt. Probeer het later opnieuw.'));
      return false;
    }
  }

  return {ondersteund, iOSnietGeinstalleerd, aanzetten};
})();
