/* AfterSermon service worker — ontvangt push-meldingen en opent de app bij klik. */
self.addEventListener('push', event => {
  let data = {};
  try { data = event.data.json(); } catch (e) {}
  const titel = data.title || 'AfterSermon';
  event.waitUntil(self.registration.showNotification(titel, {
    body: data.body || '',
    icon: '/static/icon.svg',
    badge: '/static/icon.svg',
    data: { url: data.url || '/' }
  }));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(clients.matchAll({type:'window'}).then(lijst => {
    for (const c of lijst) { if (c.url.includes(url) && 'focus' in c) return c.focus(); }
    return clients.openWindow(url);
  }));
});
