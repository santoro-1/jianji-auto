(() => {
  'use strict';
  const el = id => document.getElementById(id);
  let busy = false;
  let state = 'LOADING';
  let timer = null;
  const resuming = new Set();
  const descriptions = {
    UNREGISTERED: ['尚未申请设备授权', '为这台处理机提交一次申请，管理员批准后即可使用。', 'warning'],
    PENDING: ['等待管理员批准', '申请已经提交，无需再次申请或重新安装。批准后会自动继续校验。', 'warning'],
    ACTIVE: ['设备已授权', '原设备身份已确认。正常覆盖更新、移动目录和重新登录无需重复激活。', 'ok'],
    OFFLINE_GRACE: ['暂时无法联网校验', '仅能在已有短期凭据的有效范围内使用获准功能；不会重新开始宽限期。', 'warning'],
    AUTH_REFRESH_REQUIRED: ['需要重新校验授权', '这是凭据刷新，不是重新激活。请保持联网后重新校验。', 'warning'],
    REJECTED: ['设备申请未获批准', '请联系管理员核对申请，不要重复申请。', 'error'],
    SUSPENDED: ['设备授权已暂停', '请联系管理员恢复授权；重新安装不会解除暂停。', 'error'],
    REVOKED: ['设备授权已撤销', '请联系管理员办理授权或换机，原授权不会因重新安装恢复。', 'error'],
    EXPIRED: ['设备授权已到期', '请联系管理员确认授权期限。', 'warning'],
    KEY_UNAVAILABLE: ['无法读取本机设备密钥', '请先检查系统权限或 TPM 状态；程序不会自动删除或替换原密钥。', 'error'],
    KEY_INITIALIZING: ['正在处理 Windows 权限确认', '请在实际运行工作台的电脑上完成确认。程序保留当前初始化过程，不会重复启动或替换原密钥；完成后重新校验。', 'warning'],
    LOGIN_REQUIRED: ['请先登录数字人账号', '登录成功后会复用这台处理机已有的批准关系，不需要重新申请。', 'warning'],
    CLIENT_UPGRADE_REQUIRED: ['请更新工作台程序', '更新程序后保留原设备授权，无需管理员再次批准。', 'warning']
  };
  async function api(action = '') {
    const options = {credentials:'same-origin', cache:'no-store', headers:{}};
    if (action) {
      options.method = 'POST';
      options.headers['X-Device-Authorization-Action'] = '1';
      if (action === '/apply' || action === '/apply-software') {
        options.headers['Content-Type'] = 'application/json';
        const application = {label:el('label').value.trim(), confirm_initialize:true};
        if (action === '/apply-software') application.confirm_software = true;
        options.body = JSON.stringify(application);
      }
      if (action === '/repair-key-access') {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify({confirm_repair:true});
      }
    }
    const response = await fetch('/api/new/device-authorization' + action, options);
    const body = await response.json().catch(() => ({}));
    if (response.status === 401 && (!body.code || body.code === 'LOGIN_REQUIRED')) body.state = 'LOGIN_REQUIRED';
    if (!response.ok && !body.state) body.state = 'AUTH_REFRESH_REQUIRED';
    if (!body.state) throw new Error('处理机没有返回有效的授权状态，请更新兼容版本的程序。');
    return body;
  }
  function render(data) {
    state = data.state;
    let info = descriptions[state] || ['授权状态暂不可用', '请重新校验或联系管理员检查服务配置。', 'warning'];
    if (data.code === 'DEVICE_TRUST_NOT_CONFIGURED') info = ['此程序尚未配置正式授权', '请使用包含正式验证公钥的工作台版本。重复申请设备不会解决程序配置问题。', 'warning'];
    if (data.code === 'DEVICE_SOFTWARE_NOT_ALLOWED') info = ['尚未允许软件兼容保护', '请先由网站管理员为此账号允许软件保护，再重新校验并明确申请；本次没有创建或替换设备密钥。', 'warning'];
    el('status-title').textContent = info[0];
    el('status-description').textContent = info[1];
    el('status-dot').dataset.tone = info[2];
    el('application').hidden = state !== 'UNREGISTERED';
    el('key-repair').hidden = (data.code || data.error_code) !== 'KEY_ACCESS_DENIED';
    el('login').hidden = state !== 'LOGIN_REQUIRED';
    el('continue').hidden = state !== 'ACTIVE';
    el('device-id').textContent = data.device_id || (data.thumbprint ? data.thumbprint.slice(0,16) + '…' : '尚未读取');
    el('device-id').title = data.thumbprint || '';
    el('account').textContent = data.user_id ? '账号 ID：' + data.user_id : '尚未读取账号';
    el('protection').textContent = data.protection_report === 'tpm' ? 'TPM（本机报告，未做服务器硬件证明）' : data.protection_report === 'software' ? '软件兼容保护（较弱）' : '—';
    el('expires').textContent = Number.isFinite(data.exp) ? new Date(data.exp * 1000).toLocaleString() : '—';
    el('error').hidden = !data.detail;
    el('error').textContent = typeof data.detail === 'string' ? data.detail : '';
  }
  async function loadWaitingJobs() {
    const panel = el('waiting-jobs');
    if (state === 'LOGIN_REQUIRED') {panel.hidden = true; el('waiting-list').replaceChildren(); return;}
    try {
      const response = await fetch('/api/new/device-authorization/waiting-jobs', {credentials:'same-origin',cache:'no-store'});
      if (!response.ok) {panel.hidden = true; el('waiting-list').replaceChildren(); return;}
      const result = await response.json();
      const jobs = Array.isArray(result.jobs) ? result.jobs : [];
      panel.hidden = jobs.length === 0;
      el('waiting-list').replaceChildren();
      for (const job of jobs) {
        if (typeof job.job_id !== 'string' || !/^[A-Za-z0-9_-]{1,100}$/.test(job.job_id)) continue;
        const row = document.createElement('div'); row.className = 'actions';
        const label = document.createElement('p');
        label.textContent = '任务 ' + job.job_id.slice(0,12) + ' · ' + (job.created_at || '等待继续');
        const button = document.createElement('button'); button.type = 'button'; button.textContent = '继续此任务';
        button.disabled = resuming.has(job.job_id);
        button.addEventListener('click', async () => {
          if (resuming.has(job.job_id)) return;
          resuming.add(job.job_id); button.disabled = true; el('waiting-error').hidden = true;
          try {
            const reply = await fetch('/api/jobs/' + encodeURIComponent(job.job_id) + '/resume-authorization', {
              method:'POST', credentials:'same-origin', headers:{'X-Device-Authorization-Action':'1'}
            });
            const value = await reply.json().catch(() => ({}));
            if (!reply.ok) throw new Error(typeof value.detail === 'string' ? value.detail : '暂时无法继续，请先校验设备授权。');
            await loadWaitingJobs();
          } catch (error) {el('waiting-error').textContent = error.message; el('waiting-error').hidden = false;}
          finally {resuming.delete(job.job_id); button.disabled = false;}
        });
        row.append(label, button); el('waiting-list').append(row);
      }
    } catch (_) {panel.hidden = true; el('waiting-list').replaceChildren();}
  }
  function schedule() {
    clearTimeout(timer);
    if (['PENDING','ACTIVE','AUTH_REFRESH_REQUIRED','OFFLINE_GRACE','KEY_INITIALIZING'].includes(state)) {
      timer = setTimeout(() => {if (!document.hidden) run(); else schedule();}, state === 'ACTIVE' ? 300000 : 15000);
    }
  }
  async function run(action = '') {
    if (busy) return;
    busy = true;
    el('refresh').disabled = true;
    el('apply').disabled = true;
    el('apply-software').disabled = true;
    el('repair').disabled = true;
    try {
      let data = await api(action);
      // Reading a server approval is informational; refresh obtains signed
      // credentials. This never creates a key or makes another application.
      if (!action && ['ACTIVE','AUTH_REFRESH_REQUIRED'].includes(data.state) && data.thumbprint && !data.code && !data.error_code) data = await api('/refresh');
      render(data);
      await loadWaitingJobs();
    } catch (error) {
      el('error').hidden = false;
      el('error').textContent = error.message || '网络暂时不可用，请稍后重试。';
    } finally {
      busy = false;
      if (action === '/repair-key-access') el('repair-confirm').checked = false;
      if (action === '/apply-software') el('software-confirm').checked = false;
      el('refresh').disabled = false;
      el('apply').disabled = !el('confirm').checked;
      el('apply-software').disabled = !el('confirm').checked || !el('software-confirm').checked;
      el('repair').disabled = !el('repair-confirm').checked;
      schedule();
    }
  }
  function updateApplicationButtons() {
    el('apply').disabled = busy || !el('confirm').checked;
    el('apply-software').disabled = busy || !el('confirm').checked || !el('software-confirm').checked;
  }
  el('confirm').addEventListener('change', updateApplicationButtons);
  el('software-confirm').addEventListener('change', updateApplicationButtons);
  el('apply-software').addEventListener('click', () => {
    if (state === 'UNREGISTERED' && el('confirm').checked && el('software-confirm').checked && !busy) run('/apply-software');
  });
  el('apply-form').addEventListener('submit', event => {
    event.preventDefault();
    if (state === 'UNREGISTERED' && el('confirm').checked && !busy) run('/apply');
  });
  el('refresh').addEventListener('click', () => run('/refresh'));
  el('repair-confirm').addEventListener('change', () => {el('repair').disabled = busy || !el('repair-confirm').checked;});
  el('repair-form').addEventListener('submit', event => {
    event.preventDefault();
    if (!el('key-repair').hidden && el('repair-confirm').checked && !busy) run('/repair-key-access');
  });
  document.addEventListener('visibilitychange', () => {if (!document.hidden && !busy) run();});
  window.addEventListener('pagehide', () => clearTimeout(timer));
  run();
})();
