frappe.pages['apkt-keluhan'].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({ parent: wrapper, title: 'Keluhan APKT', single_column: true });
  const esc = frappe.utils.escape_html;
  const $body = $('<div class="apkt-body"></div>').appendTo(page.main);
  let rows = [];

  const poller = page.add_field({ fieldname: 'poller', fieldtype: 'Select', label: 'Poller', change: () => load() });
  const status = page.add_field({ fieldname: 'status', fieldtype: 'Select', label: 'Status', change: () => render() });
  const search = page.add_field({ fieldname: 'q', fieldtype: 'Data', label: 'Cari', change: () => render() });
  page.set_primary_action('Muat Ulang', () => load(true), 'refresh');

  const indicator = s => /selesai/i.test(s) ? 'green' : /batal/i.test(s) ? 'red' : /konfirmasi/i.test(s) ? 'yellow' : 'blue';

  function render() {
    const q = (search.get_value() || '').toLowerCase();
    const st = status.get_value();
    const list = rows.filter(r => (!st || r.status === st) &&
      (!q || [r.no_laporan, r.nama_pelapor, r.no_meter, r.id_pelanggan, r.permasalahan].join(' ').toLowerCase().includes(q)));
    const tr = list.map((r, i) => `<tr>
      <td>${i + 1}</td><td><b>${esc(r.no_laporan || '-')}</b></td><td>${esc(r.nama_pelapor || '-')}</td>
      <td style="max-width:360px">${esc(r.permasalahan || '-')}</td><td>${esc(r.waktu_lapor || '-')}</td>
      <td><span class="indicator-pill ${indicator(r.status)}">${esc(r.status || '-')}</span></td>
      <td>${r.diam_menit == null ? '-' : esc(String(r.diam_menit)) + ' mnt'}</td>
      <td>${esc(r.ulp || '-')}</td><td>${esc(r.no_meter || '-')}<br><small class="text-muted">${esc(r.id_pelanggan || '')}</small></td>
      <td>${esc(r.alamat || '-')}</td></tr>`).join('');
    $body.find('.apkt-table').html(`<div class="table-responsive"><table class="table table-bordered table-sm">
      <thead><tr><th>No</th><th>No. Laporan</th><th>Pelapor</th><th>Permasalahan</th><th>Waktu Lapor</th>
      <th>Status</th><th>Status Sama</th><th>ULP</th><th>Meter / ID</th><th>Alamat</th></tr></thead>
      <tbody>${tr || '<tr><td colspan="10" class="text-center text-muted">Tidak ada data.</td></tr>'}</tbody></table></div>`);
  }

  function load(force) {
    return frappe.call({ method: 'apkt_monitor.api.get_keluhan',
      args: { poller: poller.get_value() || null, force: force ? 1 : 0 } }).then(r => {
      const d = r.message; rows = d.data;
      const opts = [''].concat(Object.keys(d.counts));
      status.df.options = opts.join('\n'); status.refresh();
      const summary = Object.entries(d.counts).map(([k, v]) => `<span class="indicator-pill ${indicator(k)} mr-2">${esc(k)}: ${v}</span>`).join('');
      $body.find('.apkt-head').html(`<div class="mb-2">${summary}</div>
        <div class="text-muted small">${esc(d.poller)} · ${esc(d.date_from)} s/d ${esc(d.date_to)} · total ${d.total}
        · diperbarui ${esc(d.fetched_at)}${d.truncated ? ' · <b>data melebihi batas halaman</b>' : ''}</div>`);
      render();
    });
  }

  $body.html('<div class="apkt-head"></div><div class="apkt-table"></div>');
  frappe.call('apkt_monitor.api.list_pollers').then(r => {
    poller.df.options = r.message.map(p => p.name).join('\n'); poller.refresh();
    if (r.message.length) poller.set_value(r.message[0].name);
    load();
  });
  const timer = setInterval(() => { if (document.body.contains(wrapper) && $(wrapper).is(':visible')) load(); }, 60000);
  $(wrapper).on('remove', () => clearInterval(timer));
};
