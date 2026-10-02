// ==UserScript==
// @name         AniBT 已整理标记同步 (Anime-Manager)
// @namespace    https://github.com/anime-manager
// @version      1.1.0
// @description  在 AniBT 页面上一键把番剧标记为「已整理」，同步到自己部署的 Anime-Manager (bgm_user_mark)。项目本身零改动。
// @match        https://anibt.net/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_registerMenuCommand
// @connect      *
// @run-at       document-idle
// ==/UserScript==

(function () {
    'use strict';

    const MARK_STATUS = 'organized';
    const MARKS_TTL = 60 * 1000; // 标记缓存有效期，避免 SPA 切页频繁请求

    let marksCache = null;      // { ts, Set<bgm_id> }
    let detailBtn = null;       // 详情页浮动按钮引用，路由离开时移除
    let configBtn = null;       // 未配置时的提示按钮
    let configErrorShown = false;

    // ------------------------------------------------------------ 配置
    function getCfg() {
        return {
            server: (GM_getValue('am_server', '') || '').replace(/\/+$/, ''),
            token: GM_getValue('am_token', '') || '',
        };
    }

    GM_registerMenuCommand('⚙️ 配置 Anime-Manager 连接', openConfigModal);
    GM_registerMenuCommand('🔄 强制刷新标记缓存', forceRefresh);

    function forceRefresh() {
        marksCache = null;
        configErrorShown = false;
        inject();
        toast('已重新加载标记', 'ok');
    }

    // ------------------------------------------------------------ 请求
    function gmRequest(method, path, body, cfgOverride) {
        const cfg = cfgOverride || getCfg();
        const server = (cfg.server || '').replace(/\/+$/, '');
        const token = cfg.token || '';
        return new Promise((resolve, reject) => {
            if (!server || !token) {
                reject(new Error('NO_CONFIG'));
                return;
            }
            GM_xmlhttpRequest({
                method,
                url: server + path,
                headers: Object.assign(
                    { Authorization: 'Bearer ' + token },
                    body !== undefined ? { 'Content-Type': 'application/json' } : {},
                ),
                data: body !== undefined ? JSON.stringify(body) : undefined,
                timeout: 15000,
                onload(res) {
                    let data = null;
                    try { data = JSON.parse(res.responseText); } catch (e) { /* ignore */ }
                    if (res.status === 401 || res.status === 403) {
                        reject(new Error('鉴权失败 (' + res.status + ')，请检查 API Key'));
                    } else if (res.status >= 200 && res.status < 300) {
                        resolve(data);
                    } else {
                        const detail = data && (data.detail || data.message);
                        reject(new Error('HTTP ' + res.status + (detail ? ': ' + detail : '')));
                    }
                },
                onerror() { reject(new Error('网络错误，无法连接 ' + server)); },
                ontimeout() { reject(new Error('请求超时')); },
            });
        });
    }

    async function loadMarks(force = false) {
        if (!force && marksCache && Date.now() - marksCache.ts < MARKS_TTL) {
            return marksCache.set;
        }
        const data = await gmRequest('GET', '/api/bangumi/mark');
        const set = new Set();
        for (const row of (data && data.data) || []) {
            if (row.status === MARK_STATUS) set.add(Number(row.bgm_id));
        }
        marksCache = { ts: Date.now(), set };
        return set;
    }

    async function setMark(bgmId, organized) {
        await gmRequest('POST', '/api/bangumi/mark/' + bgmId, {
            status: organized ? MARK_STATUS : null,
        });
        if (marksCache) {
            if (organized) marksCache.set.add(Number(bgmId));
            else marksCache.set.delete(Number(bgmId));
            marksCache.ts = Date.now();
        }
    }

    // ------------------------------------------------------------ 样式
    const CSS = `
.am-mark-badge {
    position: absolute; top: 6px; right: 6px; z-index: 30;
    width: 24px; height: 24px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 700; line-height: 1;
    cursor: pointer; user-select: none; pointer-events: auto;
    background: rgba(20, 20, 26, .55); color: rgba(255, 255, 255, .45);
    border: 1.5px solid rgba(255, 255, 255, .35);
    backdrop-filter: blur(2px);
    transition: opacity .15s, transform .15s, background .15s;
    opacity: .55;
}
.am-mark-badge:hover { opacity: 1; transform: scale(1.15); }
.am-mark-badge.am-marked {
    background: rgba(46, 160, 67, .92); color: #fff;
    border-color: rgba(46, 160, 67, .92); opacity: .9;
}
.am-mark-btn {
    position: fixed; right: 22px; bottom: 74px; z-index: 99990;
    padding: 9px 16px; border-radius: 22px;
    font-size: 13px; font-weight: 600; letter-spacing: .5px;
    cursor: pointer; user-select: none;
    background: rgba(30, 30, 38, .92); color: rgba(255, 255, 255, .85);
    border: 1px solid rgba(255, 255, 255, .22);
    box-shadow: 0 4px 16px rgba(0, 0, 0, .45);
    backdrop-filter: blur(4px);
    transition: background .15s, color .15s;
}
.am-mark-btn:hover { background: rgba(50, 50, 62, .95); }
.am-mark-btn.am-marked {
    background: rgba(46, 160, 67, .95); color: #fff;
    border-color: rgba(46, 160, 67, .95);
}
.am-mark-btn.am-config { bottom: 22px; color: #ffb454; }
#am-toast-wrap {
    position: fixed; bottom: 26px; left: 50%; transform: translateX(-50%);
    z-index: 100001; display: flex; flex-direction: column; gap: 8px; align-items: center;
    pointer-events: none;
}
.am-toast {
    padding: 8px 18px; border-radius: 8px; font-size: 13px;
    color: #fff; background: rgba(40, 40, 50, .95);
    box-shadow: 0 4px 14px rgba(0, 0, 0, .5);
    animation: am-toast-in .2s ease;
}
.am-toast.am-err { background: rgba(180, 50, 50, .95); }
.am-toast.am-ok { background: rgba(46, 130, 67, .95); }
@keyframes am-toast-in { from { opacity: 0; transform: translateY(8px); } }

/* ---------- 弹窗 ---------- */
#am-modal-overlay {
    position: fixed; inset: 0; z-index: 100000;
    background: rgba(8, 8, 12, .6);
    display: flex; align-items: center; justify-content: center;
    backdrop-filter: blur(3px);
    animation: am-fade .18s ease;
}
.am-modal {
    width: 400px; max-width: calc(100vw - 40px);
    max-height: calc(100vh - 60px); overflow-y: auto;
    background: linear-gradient(165deg, #23232e 0%, #1a1a22 100%);
    border: 1px solid rgba(255, 255, 255, .12);
    border-radius: 14px; padding: 24px;
    box-shadow: 0 16px 48px rgba(0, 0, 0, .6);
    font-size: 14px; color: rgba(255, 255, 255, .88);
    box-sizing: border-box;
    animation: am-pop .22s cubic-bezier(.2, .9, .3, 1.2);
}
.am-modal h3 { margin: 0 0 6px; font-size: 16px; font-weight: 700; color: #fff; }
.am-modal .am-desc { color: rgba(255, 255, 255, .5); font-size: 12px; line-height: 1.6; margin: 0 0 16px; }
.am-field { margin-bottom: 14px; }
.am-field label {
    display: block; font-size: 12px; font-weight: 600;
    color: rgba(255, 255, 255, .6); margin-bottom: 6px; letter-spacing: .3px;
}
.am-field input {
    width: 100%; box-sizing: border-box; padding: 10px 12px;
    border-radius: 9px; border: 1px solid rgba(255, 255, 255, .15);
    background: rgba(255, 255, 255, .05); color: #fff; font-size: 13px;
    outline: none; transition: border-color .15s, background .15s;
}
.am-field input::placeholder { color: rgba(255, 255, 255, .25); }
.am-field input:focus { border-color: #5b9dff; background: rgba(255, 255, 255, .08); }
.am-modal-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; align-items: center; }
.am-modal-actions .am-status { margin-right: auto; font-size: 12px; }
.am-status.am-ok { color: #5ad07a; }
.am-status.am-err { color: #ff7b7b; }
.am-status.am-busy { color: rgba(255, 255, 255, .45); }
.am-btn {
    padding: 9px 18px; border-radius: 9px; font-size: 13px; font-weight: 600;
    cursor: pointer; border: 1px solid transparent;
    transition: background .15s, transform .1s;
}
.am-btn:active { transform: scale(.97); }
.am-btn-primary { background: #3b82f6; color: #fff; }
.am-btn-primary:hover { background: #2f6fe0; }
.am-btn-ghost {
    background: rgba(255, 255, 255, .08); color: rgba(255, 255, 255, .78);
    border-color: rgba(255, 255, 255, .12);
}
.am-btn-ghost:hover { background: rgba(255, 255, 255, .14); }
.am-btn-danger { background: #d64545; color: #fff; }
.am-btn-danger:hover { background: #c03a3a; }
.am-confirm-msg { margin: 4px 0 0; line-height: 1.7; }
@keyframes am-fade { from { opacity: 0; } }
@keyframes am-pop { from { opacity: 0; transform: scale(.94) translateY(10px); } }
`;

    function ensureStyle() {
        if (document.getElementById('am-mark-style')) return;
        const style = document.createElement('style');
        style.id = 'am-mark-style';
        style.textContent = CSS;
        document.head.appendChild(style);
    }

    function toast(message, type) {
        ensureStyle();
        let wrap = document.getElementById('am-toast-wrap');
        if (!wrap) {
            wrap = document.createElement('div');
            wrap.id = 'am-toast-wrap';
            document.body.appendChild(wrap);
        }
        const item = document.createElement('div');
        item.className = 'am-toast' + (type === 'err' ? ' am-err' : type === 'ok' ? ' am-ok' : '');
        item.textContent = message;
        wrap.appendChild(item);
        setTimeout(() => item.remove(), type === 'err' ? 6000 : 3000);
    }

    // ------------------------------------------------------------ 弹窗基础
    function openModal() {
        ensureStyle();
        const overlay = document.createElement('div');
        overlay.id = 'am-modal-overlay';
        document.body.appendChild(overlay);
        const close = () => {
            overlay.removeEventListener('keydown', onKey, true);
            window.removeEventListener('keydown', onKey, true);
            overlay.remove();
        };
        const onKey = (e) => {
            if (e.key === 'Escape') { e.stopPropagation(); close(); }
        };
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) close(); // 点遮罩关闭
        });
        window.addEventListener('keydown', onKey, true);
        return { overlay, close };
    }

    // 确认框 (Promise<boolean>)
    function confirmDialog({ title, message, confirmText = '确认', danger = false }) {
        return new Promise((resolve) => {
            const { overlay, close } = openModal();
            const box = document.createElement('div');
            box.className = 'am-modal';
            box.innerHTML =
                '<h3></h3><p class="am-confirm-msg"></p>' +
                '<div class="am-modal-actions">' +
                '<button class="am-btn am-btn-ghost" data-act="no">取消</button>' +
                '<button class="am-btn ' + (danger ? 'am-btn-danger' : 'am-btn-primary') + '" data-act="yes"></button>' +
                '</div>';
            box.querySelector('h3').textContent = title || '确认操作';
            box.querySelector('.am-confirm-msg').textContent = message || '';
            box.querySelector('[data-act="yes"]').textContent = confirmText;
            box.querySelector('[data-act="yes"]').addEventListener('click', () => { close(); resolve(true); });
            box.querySelector('[data-act="no"]').addEventListener('click', () => { close(); resolve(false); });
            overlay.appendChild(box);
            box.querySelector('[data-act="yes"]').focus();
        });
    }

    // 配置弹窗: 地址 + API Key 一个表单, 带连接测试
    function openConfigModal() {
        const { overlay, close } = openModal();
        const cfg = getCfg();
        const box = document.createElement('div');
        box.className = 'am-modal';
        box.innerHTML =
            '<h3>⚙️ 配置 Anime-Manager 连接</h3>' +
            '<p class="am-desc">填写你部署的 Anime-Manager 地址和 API Key（项目「系统设置」里的 external_token）。配置仅保存在本浏览器。</p>' +
            '<div class="am-field"><label>服务器地址</label>' +
            '<input id="am-cfg-server" type="text" placeholder="http://192.168.50.252:8000" spellcheck="false"></div>' +
            '<div class="am-field"><label>API Key (external_token)</label>' +
            '<input id="am-cfg-token" type="password" placeholder="系统设置里配置的令牌" spellcheck="false"></div>' +
            '<div class="am-modal-actions">' +
            '<span class="am-status"></span>' +
            '<button class="am-btn am-btn-ghost" data-act="test">测试连接</button>' +
            '<button class="am-btn am-btn-ghost" data-act="cancel">取消</button>' +
            '<button class="am-btn am-btn-primary" data-act="save">保存</button>' +
            '</div>';
        overlay.appendChild(box);

        const serverInput = box.querySelector('#am-cfg-server');
        const tokenInput = box.querySelector('#am-cfg-token');
        const statusEl = box.querySelector('.am-status');
        serverInput.value = cfg.server;
        tokenInput.value = cfg.token;

        const setStatus = (text, cls) => {
            statusEl.textContent = text;
            statusEl.className = 'am-status' + (cls ? ' ' + cls : '');
        };

        const readInputs = () => ({
            server: serverInput.value.trim().replace(/\/+$/, ''),
            token: tokenInput.value.trim(),
        });

        const save = async () => {
            const values = readInputs();
            if (!values.server || !values.token) {
                setStatus('请填写完整的服务器地址和 API Key', 'am-err');
                return;
            }
            GM_setValue('am_server', values.server);
            GM_setValue('am_token', values.token);
            marksCache = null;
            configErrorShown = false;
            close();
            toast('配置已保存，正在验证连接...', 'ok');
            try {
                const set = await loadMarks(true);
                toast('连接成功，当前已有 ' + set.size + ' 个已整理标记', 'ok');
            } catch (err) {
                toast('连接测试失败: ' + err.message, 'err');
            }
            inject();
        };

        const testConnection = async () => {
            const values = readInputs();
            if (!values.server || !values.token) {
                setStatus('请先填写完整', 'am-err');
                return;
            }
            setStatus('正在连接...', 'am-busy');
            try {
                const data = await gmRequest('GET', '/api/bangumi/mark', undefined, values);
                const count = ((data && data.data) || []).length;
                setStatus('✓ 连接成功，共 ' + count + ' 个标记', 'am-ok');
            } catch (err) {
                setStatus('✗ ' + err.message, 'am-err');
            }
        };

        box.querySelector('[data-act="save"]').addEventListener('click', save);
        box.querySelector('[data-act="cancel"]').addEventListener('click', close);
        box.querySelector('[data-act="test"]').addEventListener('click', testConnection);
        box.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && e.target.tagName === 'INPUT') save();
        });
        serverInput.focus();
    }

    function showConfigButton() {
        if (configBtn && document.body.contains(configBtn)) return;
        ensureStyle();
        configBtn = document.createElement('div');
        configBtn.className = 'am-mark-btn am-config';
        configBtn.textContent = '⚙ AniBT 同步未配置，点击设置';
        configBtn.addEventListener('click', openConfigModal);
        document.body.appendChild(configBtn);
    }

    function removeConfigButton() {
        if (configBtn) { configBtn.remove(); configBtn = null; }
    }

    // ------------------------------------------------------------ 标记切换
    async function toggleMark(bgmId, onDone) {
        const marks = await loadMarks();
        const organized = marks.has(Number(bgmId));
        if (organized) {
            const yes = await confirmDialog({
                title: '取消已整理标记',
                message: '确定要取消该番剧的「已整理」标记吗?',
                confirmText: '取消标记',
                danger: true,
            });
            if (!yes) return;
        }
        // 乐观更新
        if (organized) marks.delete(Number(bgmId));
        else marks.add(Number(bgmId));
        refreshBadgeState(bgmId);
        onDone && onDone(!organized);
        try {
            await setMark(bgmId, !organized);
            toast(!organized ? '已标记为已整理' : '已取消标记', 'ok');
        } catch (err) {
            // 回滚
            if (organized) marks.add(Number(bgmId));
            else marks.delete(Number(bgmId));
            refreshBadgeState(bgmId);
            onDone && onDone(organized);
            toast('同步失败: ' + err.message, 'err');
        }
    }

    function refreshBadgeState(bgmId) {
        const marks = marksCache ? marksCache.set : new Set();
        const marked = marks.has(Number(bgmId));
        document.querySelectorAll('[data-amark-id="' + bgmId + '"]').forEach(el => {
            el.classList.toggle('am-marked', marked);
            el.textContent = marked ? '✓' : '+';
            el.title = marked ? '已整理 · 点击取消' : '标记为已整理';
        });
        if (detailBtn && String(detailBtn.dataset.amarkId) === String(bgmId)) {
            detailBtn.classList.toggle('am-marked', marked);
            detailBtn.textContent = marked ? '✓ 已整理' : '标记已整理';
            detailBtn.title = marked ? '点击取消标记' : '同步到 Anime-Manager';
        }
    }

    // ------------------------------------------------------------ 注入: 详情页
    async function injectDetail(bgmId, marks) {
        ensureStyle();
        removeConfigButton();
        if (!detailBtn) {
            detailBtn = document.createElement('div');
            detailBtn.className = 'am-mark-btn';
            detailBtn.addEventListener('click', () => toggleMark(bgmId));
            document.body.appendChild(detailBtn);
        }
        detailBtn.dataset.amarkId = bgmId;
        refreshBadgeState(bgmId);
    }

    function removeDetailButton() {
        if (detailBtn) { detailBtn.remove(); detailBtn = null; }
    }

    // ------------------------------------------------------------ 注入: 季度页
    async function injectSeasonal(marks) {
        ensureStyle();
        removeConfigButton();
        // 同一部番可能有多个链接(海报/标题), 按 bgmId 分组, 只往面积最大的链接注入一个角标
        const byId = new Map();
        for (const a of document.querySelectorAll('a[href*="/anime/"]')) {
            const match = (a.getAttribute('href') || '').match(/\/anime\/(\d+)/);
            if (!match) continue;
            const bgmId = Number(match[1]);
            const rect = a.getBoundingClientRect();
            const area = rect.width * rect.height;
            if (!byId.has(bgmId)) byId.set(bgmId, []);
            byId.get(bgmId).push({ a, area, hasImg: !!a.querySelector('img') });
        }
        for (const [bgmId, candidates] of byId) {
            candidates.sort((x, y) => (y.hasImg - x.hasImg) || (y.area - x.area));
            const target = candidates[0].a;
            let badge = target.querySelector(':scope [data-amark]');
            if (badge) {
                refreshBadgeState(bgmId);
                continue;
            }
            badge = document.createElement('div');
            badge.className = 'am-mark-badge';
            badge.dataset.amark = '1';
            badge.dataset.amarkId = bgmId;
            badge.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                toggleMark(bgmId);
            }, true); // 捕获阶段拦截, 避免触发 SPA 路由跳转
            if (getComputedStyle(target).position === 'static') {
                target.style.position = 'relative';
            }
            target.appendChild(badge);
            refreshBadgeState(bgmId);
        }
    }

    // ------------------------------------------------------------ 路由调度
    let injecting = false;

    async function inject() {
        if (injecting) return;
        injecting = true;
        try {
            const marks = await loadMarks().catch((err) => {
                if (err.message === 'NO_CONFIG') showConfigButton();
                else if (!configErrorShown) {
                    configErrorShown = true;
                    toast('Anime-Manager 标记加载失败: ' + err.message, 'err');
                }
                return null;
            });
            if (!marks) return;

            const animeMatch = location.pathname.match(/^\/anime\/(\d+)/);
            if (animeMatch) {
                await injectDetail(Number(animeMatch[1]), marks);
            } else {
                removeDetailButton();
            }
            if (location.pathname.startsWith('/seasonal')) {
                await injectSeasonal(marks);
            }
        } finally {
            injecting = false;
        }
    }

    function debounce(fn, ms) {
        let timer = null;
        return () => {
            clearTimeout(timer);
            timer = setTimeout(fn, ms);
        };
    }

    function start() {
        ensureStyle();
        inject();
        // anibt 是 SPA: 监听 DOM 变化, 路由切换/新卡片渲染后重新注入
        const observer = new MutationObserver(debounce(inject, 300));
        observer.observe(document.body, { childList: true, subtree: true });
        window.addEventListener('popstate', inject);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
    }
})();
