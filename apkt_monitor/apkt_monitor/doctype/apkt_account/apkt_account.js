frappe.ui.form.on('APKT Account', {
  refresh(frm) {
    if (frm.is_new()) return;
    frm.add_custom_button('Login APKT', () => {
      const d = new frappe.ui.Dialog({
        title: 'Login Server APKT',
        fields: [
          { fieldname: 'password', fieldtype: 'Password', label: 'Password', reqd: 1 },
          { fieldname: 'captcha_img', fieldtype: 'HTML' },
          { fieldname: 'reload', fieldtype: 'Button', label: 'Muat Ulang Captcha', click: () => load() },
          { fieldname: 'captcha', fieldtype: 'Data', label: 'Kode Captcha', reqd: 1 }
        ],
        primary_action_label: 'Login',
        primary_action(v) {
          frappe.call({
            method: 'apkt_monitor.api.login',
            args: { account: frm.doc.name, password: v.password, captcha: v.captcha },
            freeze: true
          }).then(() => { d.hide(); frm.reload_doc(); frappe.show_alert({ message: 'Login APKT berhasil', indicator: 'green' }); },
                  () => load());
        }
      });
      const load = () => frappe.call('apkt_monitor.api.get_captcha', { account: frm.doc.name }).then(r => {
        const img = document.createElement('img');
        img.src = r.message.image; img.style.maxHeight = '64px';
        d.get_field('captcha_img').$wrapper.empty().append(img);
      });
      d.show(); load();
    });
  }
});
