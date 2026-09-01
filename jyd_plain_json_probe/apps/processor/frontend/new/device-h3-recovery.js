(() => {
  'use strict';
  const el = id => document.getElementById(id);
  const validId = value => typeof value === 'string' && /^[A-Za-z0-9_-]{1,64}$/.test(value);
  let cursor = null, loading = false, sending = false, checking = false, pending = null;
  const batches = new Map();
  function failure(error) {el('h3-waiting-error').textContent = error.message; el('h3-waiting-error').hidden = false;}
  async function api(path, payload) {
    const options = {credentials:'same-origin', cache:'no-store', headers:{}};
    if (payload !== undefined) {
      options.method = 'POST'; options.headers = {'Content-Type':'application/json','X-Device-Authorization-Action':'1'};
      options.body = JSON.stringify(payload);
    }
    const response = await fetch('/api/new/device-authorization/' + path, options);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(typeof body.detail === 'string' ? body.detail : '云端任务查询失败，请检查登录和服务器版本。');
      error.code = body.code || ''; throw error;
    }
    return body;
  }
  function render() {
    el('h3-waiting-list').replaceChildren();
    for (const batch of batches.values()) {
      const row = document.createElement('div'); row.className = 'actions';
      const title = document.createElement('p'); title.textContent = (batch.name || batch.batch_id) + ' · ' + batch.segment_count + ' 段等待授权';
      title.style.overflowWrap = 'anywhere';
      const button = document.createElement('button'); button.type = 'button'; button.textContent = '查看并继续'; button.disabled = sending || checking;
      button.addEventListener('click', () => inspect(batch.batch_id)); row.append(title, button); el('h3-waiting-list').append(row);
    }
    el('h3-waiting-more').hidden = !cursor;
    el('h3-waiting-status').textContent = batches.size ? '已找到 ' + batches.size + ' 个批次；请逐个确认。' : cursor ? '本页没有待恢复批次，可继续查询后续批次。' : '当前没有需要手动补授权的云端批次。';
  }
  async function load(more = false) {
    if (loading) return;
    loading = true; el('h3-waiting-refresh').disabled = true; el('h3-waiting-more').disabled = true;
    try {
      const result = await api('h3-waiting' + (more && cursor ? '?after_id=' + encodeURIComponent(cursor) : ''));
      if (result.schema !== 'runninghub.h3-authorization-recovery.v1' || !Array.isArray(result.batches)) throw new Error('服务器尚不支持安全恢复，请先更新兼容版本。');
      if (!more) batches.clear();
      for (const batch of result.batches) if (validId(batch.batch_id) && Number.isInteger(batch.segment_count) && batch.segment_count > 0) batches.set(batch.batch_id, batch);
      cursor = validId(result.next_cursor) ? result.next_cursor : null; render();
    } catch (error) {failure(error); el('h3-waiting-status').textContent = '本次查询未成功，不会自动恢复任何任务。';}
    finally {loading = false; el('h3-waiting-refresh').disabled = false; el('h3-waiting-more').disabled = false;}
  }
  function requestKey() {
    const bytes = new Uint8Array(16); crypto.getRandomValues(bytes);
    return 'h3-resume-' + Array.from(bytes, byte => byte.toString(16).padStart(2,'0')).join('');
  }
  async function inspect(batchId) {
    if (sending || checking) return;
    checking = true; pending = null; el('h3-recovery-review').hidden = true; el('h3-waiting-error').hidden = true; render();
    el('h3-recovery-confirm').checked = false; el('h3-recovery-submit').disabled = true;
    try {
      const value = await api('h3/' + encodeURIComponent(batchId) + '/prepare', {});
      if (value.schema !== 'runninghub.h3-authorization-recovery.v1' || value.batch_id !== batchId || !value.can_resume || !Array.isArray(value.segments) || !Number.isInteger(value.segment_count) || value.segment_count < 1 || value.segment_count !== value.segments.length || !/^[a-f0-9]{64}$/.test(value.review_token)) throw new Error('待恢复分段已变化，请刷新云端列表后再查看。');
      pending = {batchId, reviewToken:value.review_token, requestKey:requestKey()};
      el('h3-recovery-title').textContent = (value.name || batchId) + '：继续 ' + value.segment_count + ' 个原分段';
      el('h3-recovery-segments').replaceChildren();
      for (const segment of value.segments) {
        const line = document.createElement('p'); line.textContent = '第 ' + segment.row_id + ' 行 · 第 ' + segment.segment_number + ' 段'; line.style.overflowWrap = 'anywhere'; el('h3-recovery-segments').append(line);
      }
      el('h3-recovery-confirm').checked = false; el('h3-recovery-submit').disabled = true; el('h3-recovery-review').hidden = false;
    } catch (error) {failure(error);}
    finally {checking = false; render();}
  }
  el('h3-recovery-confirm').addEventListener('change', () => {el('h3-recovery-submit').disabled = sending || !pending || !el('h3-recovery-confirm').checked;});
  el('h3-recovery-cancel').addEventListener('click', () => {if (!sending) {pending = null; el('h3-recovery-review').hidden = true;}});
  el('h3-recovery-submit').addEventListener('click', async () => {
    if (sending || !pending || !el('h3-recovery-confirm').checked) return;
    const selected = pending; sending = true; el('h3-recovery-submit').disabled = true; el('h3-recovery-cancel').disabled = true; el('h3-waiting-error').hidden = true; render();
    try {
      const result = await api('h3/' + encodeURIComponent(selected.batchId) + '/resume', {resume_confirmed:true, request_key:selected.requestKey, review_token:selected.reviewToken});
      if (result.schema !== 'runninghub.h3-authorization-recovery.v1' || result.batch_id !== selected.batchId) throw new Error('没有收到有效恢复回执。可重试同一确认，不要新建批次。');
      pending = null; el('h3-recovery-review').hidden = true; await load();
    } catch (error) {
      failure(error);
      // A lost response retains the same business key. A changed review requires
      // another explicit inspection; neither condition automatically resubmits.
      if (['H3_RECOVERY_REVIEW_CHANGED','H3_RECOVERY_REQUEST_CONFLICT'].includes(error.code)) {pending = null; el('h3-recovery-review').hidden = true;}
    } finally {sending = false; el('h3-recovery-cancel').disabled = false; el('h3-recovery-submit').disabled = !pending || !el('h3-recovery-confirm').checked; render();}
  });
  el('h3-waiting-refresh').addEventListener('click', () => {el('h3-waiting-error').hidden = true; load();});
  el('h3-waiting-more').addEventListener('click', () => load(true));
  load();
})();
