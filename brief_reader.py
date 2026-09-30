#!/usr/bin/env python3
"""Local, dependency-free reader for dated HTML briefs in this directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import signal
import sys
import threading
import webbrowser
from datetime import datetime
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.parse import unquote, urlparse
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent
if sys.platform == "win32":
    CACHE_BASE = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
elif sys.platform == "darwin":
    CACHE_BASE = Path.home() / "Library" / "Caches"
else:
    CACHE_BASE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
CACHE_DIR = CACHE_BASE / "DailyBriefReader"
RUNTIME_FILE = CACHE_DIR / f"runtime-{hashlib.sha256(str(ROOT).encode('utf-8')).hexdigest()[:12]}.json"
BRIEF_PATTERN = re.compile(r"^(20\d{2}-\d{2}-\d{2})\.html$")
APP_ID = "daily-brief-reader"
DEFAULT_PORT = 8877
MAX_PORT = 8897


APP_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>每日简报</title>
  <style>
    :root {
      --ink: #13222e;
      --muted: #6d7780;
      --paper: #f7f5ef;
      --panel: rgba(255,255,255,.88);
      --line: rgba(21,35,47,.11);
      --blue: #3167e3;
      --green: #15946f;
      --shadow: 0 20px 60px rgba(29,44,56,.14);
      --sidebar: 342px;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; }
    body {
      margin: 0;
      overflow: hidden;
      color: var(--ink);
      background:
        radial-gradient(circle at 8% -10%, rgba(49,103,227,.15), transparent 34rem),
        linear-gradient(145deg, #e9edee, #f3f1eb);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
        "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      -webkit-font-smoothing: antialiased;
    }
    button, input { font: inherit; }
    button { color: inherit; }
    .app { display: grid; grid-template-columns: var(--sidebar) minmax(0, 1fr); grid-template-rows: minmax(0, 1fr); height: 100%; transition: grid-template-columns .18s ease; }
    .sidebar {
      position: relative;
      z-index: 3;
      display: flex;
      min-width: 0;
      min-height: 0;
      flex-direction: column;
      padding: 22px 18px 18px;
      background: rgba(247,245,239,.93);
      border-right: 1px solid var(--line);
      backdrop-filter: blur(18px);
    }
    .brand { display: flex; align-items: center; gap: 12px; padding: 0 6px 18px; }
    .brand-mark {
      display: grid;
      width: 43px;
      height: 43px;
      place-items: center;
      color: white;
      background: linear-gradient(145deg, var(--blue), #274a9d);
      border-radius: 13px;
      box-shadow: 0 8px 22px rgba(49,103,227,.28);
      font: 800 17px/1 Georgia, serif;
    }
    .brand h1 { margin: 0; font: 700 21px/1.2 Georgia, "Songti SC", serif; }
    .brand p { margin: 3px 0 0; color: var(--muted); font-size: 11px; }
    .sidebar-toggle {
      position: absolute;
      top: 30px;
      right: 11px;
      display: grid;
      width: 27px;
      height: 27px;
      place-items: center;
      padding: 0;
      color: var(--muted);
      background: transparent;
      border: 0;
      border-radius: 8px;
      cursor: pointer;
    }
    .sidebar-toggle:hover, .sidebar-toggle:focus-visible { color: var(--blue); background: rgba(49,103,227,.1); }
    .sidebar-toggle svg { width: 15px; height: 15px; fill: none; stroke: currentColor; stroke-width: 2; }
    @media (min-width: 821px) {
      .app.sidebar-collapsed { --sidebar: 58px; }
      .app.sidebar-collapsed .sidebar { padding: 0; }
      .app.sidebar-collapsed .brand { justify-content: center; padding: 18px 0 0; }
      .app.sidebar-collapsed .brand-mark { width: 36px; height: 36px; font-size: 14px; }
      .app.sidebar-collapsed .brand > div:last-child,
      .app.sidebar-collapsed .search-wrap,
      .app.sidebar-collapsed .archive-head,
      .app.sidebar-collapsed .list,
      .app.sidebar-collapsed .sidebar-foot { display: none; }
      .app.sidebar-collapsed .sidebar-toggle { top: 68px; right: 15px; }
      .app.sidebar-collapsed .sidebar-toggle svg { transform: rotate(180deg); }
    }
    .search-wrap { position: relative; margin-bottom: 14px; }
    .search-wrap svg {
      position: absolute;
      left: 13px;
      top: 50%;
      width: 16px;
      transform: translateY(-50%);
      color: #879198;
    }
    .search {
      width: 100%;
      height: 42px;
      padding: 0 12px 0 38px;
      color: var(--ink);
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 12px;
      outline: none;
    }
    .search:focus { border-color: rgba(49,103,227,.55); box-shadow: 0 0 0 3px rgba(49,103,227,.1); }
    .archive-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0 6px 8px;
      color: var(--muted);
      font-size: 11px;
      font-weight: 750;
      letter-spacing: .08em;
      text-transform: uppercase;
    }
    .archive-tools { display: flex; align-items: center; gap: 5px; }
    .mode-switch { display: flex; gap: 2px; padding: 2px; background: rgba(255,255,255,.65); border: 1px solid var(--line); border-radius: 9px; }
    .group-mode { width: 24px; height: 22px; padding: 0; color: var(--muted); background: transparent; border: 0; border-radius: 6px; cursor: pointer; font-size: 11px; font-weight: 800; }
    .group-mode[aria-pressed="true"] { color: var(--blue); background: var(--blue-soft, #e9efff); }
    .group-mode:hover { color: var(--blue); }
    .refresh {
      display: grid;
      width: 27px;
      height: 27px;
      place-items: center;
      padding: 0;
      color: var(--muted);
      background: transparent;
      border: 0;
      border-radius: 8px;
      cursor: pointer;
    }
    .refresh:hover { color: var(--blue); background: rgba(49,103,227,.08); }
    .refresh svg { width: 15px; }
    .refresh:disabled { opacity: .35; cursor: default; }
    .refresh:disabled:hover { color: var(--muted); background: transparent; }
    .list { flex: 1; min-height: 0; overflow: auto; padding: 2px 3px 20px; }
    .archive-group { margin-bottom: 8px; }
    .group-toggle { position: sticky; top: 0; z-index: 1; display: flex; width: 100%; align-items: center; gap: 7px; padding: 9px 6px 8px; color: #52616c; background: #f7f5ef; border: 0; cursor: pointer; text-align: left; font-size: 11px; font-weight: 800; }
    .group-toggle:hover { color: var(--blue); }
    .group-toggle .group-chevron { width: 13px; height: 13px; fill: none; stroke: currentColor; stroke-width: 2; transition: transform .15s ease; }
    .group-toggle[aria-expanded="false"] .group-chevron { transform: rotate(-90deg); }
    .group-label { flex: 1; }
    .group-count { color: #8a949b; font-size: 10px; font-weight: 650; }
    .item {
      display: block;
      width: 100%;
      margin: 0 0 8px;
      padding: 13px 14px;
      text-align: left;
      background: rgba(255,255,255,.7);
      border: 1px solid transparent;
      border-radius: 14px;
      cursor: pointer;
      transition: .18s ease;
    }
    .item:hover { transform: translateY(-1px); background: #fff; border-color: var(--line); }
    .item.active {
      color: white;
      background: linear-gradient(145deg, #1b3041, #223e52);
      box-shadow: 0 10px 28px rgba(22,40,54,.18);
    }
    .item-top { display: flex; justify-content: space-between; gap: 10px; align-items: center; }
    .item-date { font: 700 15px/1.2 Georgia, serif; }
    .badge {
      padding: 3px 7px;
      color: #17664f;
      background: #e5f6f0;
      border-radius: 999px;
      font-size: 9px;
      font-weight: 800;
    }
    .item.active .badge { color: #caffef; background: rgba(44,194,148,.18); }
    .item-title { margin-top: 7px; font-size: 12px; font-weight: 700; line-height: 1.45; }
    .item-summary {
      display: -webkit-box;
      margin-top: 5px;
      overflow: hidden;
      color: var(--muted);
      font-size: 10px;
      line-height: 1.45;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 2;
    }
    .item.active .item-summary { color: #afbdc7; }
    .empty { padding: 35px 18px; color: var(--muted); text-align: center; font-size: 12px; }
    .sidebar-foot {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      padding: 12px 6px 0;
      color: var(--muted);
      border-top: 1px solid var(--line);
      font-size: 10px;
    }
    .workspace { display: flex; min-width: 0; min-height: 0; flex-direction: column; padding: 14px; }
    .topbar {
      display: flex;
      min-height: 54px;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      padding: 0 15px 12px;
    }
    .current { min-width: 0; }
    .current small { display: block; color: var(--blue); font-size: 10px; font-weight: 800; letter-spacing: .12em; }
    .current strong { display: block; overflow: hidden; margin-top: 2px; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
    .action {
      height: 34px;
      padding: 0 12px;
      background: rgba(255,255,255,.75);
      border: 1px solid var(--line);
      border-radius: 10px;
      cursor: pointer;
    }
    .action:hover { background: #fff; border-color: rgba(49,103,227,.25); }
    .reader {
      position: relative;
      flex: 1;
      min-height: 0;
      overflow: hidden;
      background: #e7eaeb;
      border: 1px solid var(--line);
      border-radius: 19px;
      box-shadow: var(--shadow);
    }
    iframe { display: block; width: 100%; height: 100%; border: 0; background: #fff; }
    .loading {
      position: absolute;
      inset: 0;
      display: grid;
      place-items: center;
      color: var(--muted);
      background: var(--paper);
      font-size: 12px;
    }
    .loading[hidden] { display: none; }
    .mobile-toggle { display: none; }
    .lightbox[hidden] { display: none; }
    .lightbox {
      position: fixed;
      inset: 0;
      z-index: 100;
      display: grid;
      place-items: center;
      padding: 34px;
      color: #fff;
      background: rgba(8, 15, 21, .9);
      backdrop-filter: blur(12px);
    }
    .lightbox-stage {
      display: grid;
      width: min(1400px, 96vw);
      max-height: 94vh;
      grid-template-rows: minmax(0, 1fr) auto;
      gap: 12px;
      place-items: center;
    }
    .lightbox-image {
      display: block;
      max-width: 100%;
      max-height: calc(94vh - 72px);
      object-fit: contain;
      border-radius: 10px;
      background: #fff;
      box-shadow: 0 24px 80px rgba(0,0,0,.45);
    }
    .lightbox-caption {
      max-width: min(900px, 86vw);
      margin: 0;
      color: #dbe4e9;
      font-size: 12px;
      text-align: center;
    }
    .lightbox-close {
      position: absolute;
      top: 18px;
      right: 20px;
      display: grid;
      width: 42px;
      height: 42px;
      place-items: center;
      padding: 0;
      color: #fff;
      background: rgba(255,255,255,.12);
      border: 1px solid rgba(255,255,255,.22);
      border-radius: 999px;
      cursor: pointer;
      font-size: 25px;
      line-height: 1;
    }
    .lightbox-close:hover { background: rgba(255,255,255,.2); }
    @media (max-width: 820px) {
      .app { display: block; }
      .sidebar {
        position: absolute;
        inset: 0 auto 0 0;
        width: min(88vw, 350px);
        transform: translateX(-105%);
        transition: transform .2s ease;
        box-shadow: 20px 0 60px rgba(20,35,46,.18);
      }
      .app.menu .sidebar { transform: translateX(0); }
      .workspace { height: 100%; padding: 8px; }
      .sidebar-toggle { display: none; }
      .mobile-toggle { display: inline-block; }
      .topbar { padding: 0 6px 8px; }
    }
  </style>
</head>
<body>
  <div class="app" id="app">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">3D</div>
        <div><h1>每日简报</h1><p>事件视觉 · 前馈 3D/4D · 具身智能</p></div>
      </div>
      <button class="sidebar-toggle" id="sidebar-toggle" type="button" aria-label="收起历史侧栏" aria-expanded="true" title="收起历史侧栏">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 5-7 7 7 7"/></svg>
      </button>
      <div class="search-wrap">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
        <input class="search" id="search" type="search" placeholder="搜索日期或内容" autocomplete="off">
      </div>
      <div class="archive-head">
        <span>历史简报 <span id="count"></span></span>
        <div class="archive-tools">
          <div class="mode-switch" role="group" aria-label="历史简报分组方式">
            <button class="group-mode" type="button" data-mode="month" aria-pressed="true" title="按月展示">月</button>
            <button class="group-mode" type="button" data-mode="week" aria-pressed="false" title="按周展示">周</button>
          </div>
          <button class="refresh" id="collapse-groups" type="button" title="收起全部历史分组" aria-label="收起全部历史分组">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m7 14 5-5 5 5M7 20l5-5 5 5"/></svg>
          </button>
          <button class="refresh" id="refresh" title="重新扫描目录" aria-label="重新扫描目录">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/></svg>
          </button>
        </div>
      </div>
      <div class="list" id="list"><div class="empty">正在扫描简报目录…</div></div>
      <div class="sidebar-foot"><span>自动扫描 HTML</span><span id="status">—</span></div>
    </aside>

    <section class="workspace">
      <header class="topbar">
        <button class="action mobile-toggle" id="menu">历史</button>
        <div class="current"><small>正在阅读</small><strong id="current">等待载入</strong></div>
      </header>
      <div class="reader">
        <div class="loading" id="loading">正在载入最新简报…</div>
        <iframe id="frame" title="简报正文"></iframe>
      </div>
    </section>
  </div>

  <div class="lightbox" id="lightbox" role="dialog" aria-modal="true" aria-label="图片放大预览" hidden>
    <button class="lightbox-close" id="lightbox-close" type="button" aria-label="关闭图片预览">×</button>
    <div class="lightbox-stage">
      <img class="lightbox-image" id="lightbox-image" alt="">
      <p class="lightbox-caption" id="lightbox-caption"></p>
    </div>
  </div>

  <script>
    const app = document.querySelector('#app');
    const list = document.querySelector('#list');
    const search = document.querySelector('#search');
    const frame = document.querySelector('#frame');
    const current = document.querySelector('#current');
    const loading = document.querySelector('#loading');
    const count = document.querySelector('#count');
    const status = document.querySelector('#status');
    const lightbox = document.querySelector('#lightbox');
    const lightboxImage = document.querySelector('#lightbox-image');
    const lightboxCaption = document.querySelector('#lightbox-caption');
    const lightboxClose = document.querySelector('#lightbox-close');
    const sidebarToggle = document.querySelector('#sidebar-toggle');
    const collapseGroups = document.querySelector('#collapse-groups');
    let briefs = [];
    let selected = null;
    let groupMode = localStorage.getItem('daily-brief-group-mode') === 'week' ? 'week' : 'month';
    const groupOpen = new Map();

    function setSidebarCollapsed(collapsed) {
      app.classList.toggle('sidebar-collapsed', collapsed);
      sidebarToggle.setAttribute('aria-expanded', String(!collapsed));
      sidebarToggle.setAttribute('aria-label', collapsed ? '展开历史侧栏' : '收起历史侧栏');
      sidebarToggle.title = collapsed ? '展开历史侧栏' : '收起历史侧栏';
      localStorage.setItem('daily-brief-sidebar-collapsed', collapsed ? '1' : '0');
    }

    function closeLightbox() {
      if (lightbox.hidden) return;
      lightbox.hidden = true;
      lightboxImage.removeAttribute('src');
      lightboxImage.alt = '';
      lightboxCaption.textContent = '';
    }

    function openLightbox(image) {
      const figure = image.closest('figure');
      const caption = figure?.querySelector('figcaption')?.textContent?.trim();
      lightboxImage.src = image.currentSrc || image.src;
      lightboxImage.alt = image.alt || '简报图片';
      lightboxCaption.textContent = caption || image.alt || '';
      lightboxCaption.hidden = !lightboxCaption.textContent;
      lightbox.hidden = false;
      lightboxClose.focus();
    }

    function wireBriefImages() {
      const doc = frame.contentDocument;
      if (!doc) return;
      if (!doc.querySelector('#daily-brief-reader-image-style')) {
        const style = doc.createElement('style');
        style.id = 'daily-brief-reader-image-style';
        style.textContent = '.toolbar{display:none!important}img[data-reader-zoom]{cursor:zoom-in;transition:filter .18s ease,transform .18s ease}img[data-reader-zoom]:hover{filter:brightness(.96);transform:scale(1.005)}img[data-reader-zoom]:focus{outline:3px solid #3267e3;outline-offset:3px}';
        doc.head.appendChild(style);
      }
      doc.querySelectorAll('img').forEach(image => {
        if (image.dataset.noZoom) return;
        if (image.dataset.readerZoom) return;
        image.dataset.readerZoom = 'true';
        image.tabIndex = 0;
        image.setAttribute('role', 'button');
        image.setAttribute('aria-label', `放大查看：${image.alt || '简报图片'}`);
        image.title = '点击放大查看';
        image.addEventListener('click', event => { event.preventDefault(); openLightbox(image); });
        image.addEventListener('keydown', event => {
          if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); openLightbox(image); }
        });
      });
    }

    function prettyDate(value) {
      const d = new Date(value + 'T00:00:00');
      return new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' }).format(d);
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
    }

    function filteredBriefs() {
      const q = search.value.trim().toLowerCase();
      if (!q) return briefs;
      return briefs.filter(b => `${b.date} ${b.title} ${b.summary}`.toLowerCase().includes(q));
    }

    function localDateKey(date) {
      return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
    }

    function groupForDate(value) {
      if (groupMode === 'month') {
        const [year, month] = value.split('-');
        return { key: `month:${year}-${month}`, label: `${year}年${Number(month)}月` };
      }
      const start = new Date(value + 'T12:00:00');
      start.setDate(start.getDate() - (start.getDay() + 6) % 7);
      const end = new Date(start);
      end.setDate(start.getDate() + 6);
      const endYear = end.getFullYear() === start.getFullYear() ? '' : `${end.getFullYear()}年`;
      return {
        key: `week:${localDateKey(start)}`,
        label: `${start.getFullYear()}年${start.getMonth() + 1}月${start.getDate()}日—${endYear}${end.getMonth() + 1}月${end.getDate()}日`,
      };
    }

    function renderItem(brief) {
      return `<button class="item ${selected === brief.file ? 'active' : ''}" data-file="${brief.file}">
          <span class="item-top"><span class="item-date">${prettyDate(brief.date)}</span>${brief.file === briefs[0]?.file && !search.value.trim() ? '<span class="badge">最新</span>' : ''}</span>
          <span class="item-title">${escapeHtml(brief.title)}</span>
          <span class="item-summary">${escapeHtml(brief.summary || '打开查看本期完整简报')}</span>
        </button>`;
    }

    function renderList({ resetScroll = false } = {}) {
      const rows = filteredBriefs();
      const previousScroll = list.scrollTop;
      count.textContent = `· ${rows.length}`;
      collapseGroups.disabled = Boolean(search.value.trim()) || !rows.length;
      document.querySelectorAll('.group-mode').forEach(button => {
        button.setAttribute('aria-pressed', String(button.dataset.mode === groupMode));
      });
      if (!rows.length) {
        list.innerHTML = '<div class="empty">没有找到匹配的 HTML 简报</div>';
        return;
      }
      if (search.value.trim()) {
        list.innerHTML = rows.map(renderItem).join('');
      } else {
        const groups = new Map();
        rows.forEach(brief => {
          const group = groupForDate(brief.date);
          if (!groups.has(group.key)) groups.set(group.key, { ...group, items: [] });
          groups.get(group.key).items.push(brief);
        });
        list.innerHTML = [...groups.values()].map((group, index) => {
          const expanded = groupOpen.has(group.key)
            ? groupOpen.get(group.key)
            : index === 0 || group.items.some(brief => brief.file === selected);
          return `<section class="archive-group">
            <button class="group-toggle" type="button" data-group="${group.key}" aria-expanded="${expanded}" aria-label="${group.label}，${group.items.length} 期">
              <svg class="group-chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m5 9 7 7 7-7"/></svg>
              <span class="group-label">${group.label}</span><span class="group-count">${group.items.length} 期</span>
            </button>
            <div class="group-items" ${expanded ? '' : 'hidden'}>${group.items.map(renderItem).join('')}</div>
          </section>`;
        }).join('');
      }
      list.querySelectorAll('.item').forEach(el => el.addEventListener('click', () => selectBrief(el.dataset.file)));
      list.querySelectorAll('.group-toggle').forEach(button => button.addEventListener('click', () => {
        groupOpen.set(button.dataset.group, button.getAttribute('aria-expanded') !== 'true');
        renderList();
        list.querySelector(`[data-group="${button.dataset.group}"]`)?.focus();
      }));
      list.scrollTop = resetScroll ? 0 : previousScroll;
    }

    function selectBrief(file, updateHash = true) {
      const brief = briefs.find(b => b.file === file);
      if (!brief) return;
      selected = brief.file;
      groupOpen.set(groupForDate(brief.date).key, true);
      closeLightbox();
      current.textContent = `${prettyDate(brief.date)} · ${brief.title}`;
      loading.hidden = false;
      frame.src = `/files/${encodeURIComponent(brief.file)}`;
      if (updateHash) history.replaceState(null, '', `#${brief.date}`);
      renderList();
      app.classList.remove('menu');
    }

    async function scan({ preserve = true } = {}) {
      const previousLatest = briefs[0]?.file;
      const wasLatest = !selected || selected === previousLatest;
      status.textContent = '扫描中';
      try {
        const response = await fetch('/api/briefs', { cache: 'no-store' });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        briefs = await response.json();
        status.textContent = `${briefs.length} 期`;
        const hashDate = location.hash.slice(1);
        const hashBrief = briefs.find(b => b.date === hashDate);
        const selectedExists = briefs.some(b => b.file === selected);
        renderList();
        if (!selectedExists || (!preserve && briefs.length) || (wasLatest && briefs[0]?.file !== previousLatest)) {
          selectBrief(hashBrief?.file || briefs[0]?.file, false);
        }
        if (!briefs.length) {
          current.textContent = '暂无 HTML 简报';
          loading.textContent = '目录中还没有 YYYY-MM-DD.html 简报';
        }
      } catch (error) {
        status.textContent = '扫描失败';
        list.innerHTML = `<div class="empty">无法读取简报目录<br>${error.message}</div>`;
      }
    }

    frame.addEventListener('load', () => { loading.hidden = true; wireBriefImages(); });
    lightboxClose.addEventListener('click', closeLightbox);
    lightbox.addEventListener('click', event => { if (event.target === lightbox) closeLightbox(); });
    search.addEventListener('input', () => renderList({ resetScroll: true }));
    document.querySelectorAll('.group-mode').forEach(button => button.addEventListener('click', () => {
      groupMode = button.dataset.mode;
      localStorage.setItem('daily-brief-group-mode', groupMode);
      if (selected) {
        const brief = briefs.find(item => item.file === selected);
        if (brief) groupOpen.set(groupForDate(brief.date).key, true);
      }
      renderList({ resetScroll: true });
    }));
    sidebarToggle.addEventListener('click', () => setSidebarCollapsed(!app.classList.contains('sidebar-collapsed')));
    collapseGroups.addEventListener('click', () => {
      briefs.forEach(brief => groupOpen.set(groupForDate(brief.date).key, false));
      renderList({ resetScroll: true });
    });
    document.querySelector('#refresh').addEventListener('click', () => scan());
    document.querySelector('#menu').addEventListener('click', () => app.classList.toggle('menu'));
    window.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !lightbox.hidden) { closeLightbox(); return; }
      if (event.key === 'Escape') app.classList.remove('menu');
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'f') { event.preventDefault(); search.focus(); }
    });
    setSidebarCollapsed(localStorage.getItem('daily-brief-sidebar-collapsed') === '1');
    scan({ preserve: false });
    setInterval(() => scan(), 60000);
  </script>
</body>
</html>
"""


class BriefMetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[bool] = []
        self.in_title = False
        self.capture_summary = False
        self.title_parts: list[str] = []
        self.summary_parts: list[str] = []
        self.fallback_parts: list[str] = []
        self.item_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        parent_headline = self.stack[-1] if self.stack else False
        classes = values.get("class", "").split()
        in_headline = parent_headline or "headline-box" in classes
        self.stack.append(in_headline)
        if tag == "title":
            self.in_title = True
        if tag == "p" and in_headline:
            self.capture_summary = True
        if values.get("data-item-key"):
            self.item_count += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag == "p" and self.capture_summary:
            self.capture_summary = False
        if self.stack:
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        if self.in_title:
            self.title_parts.append(text)
        if self.capture_summary:
            self.summary_parts.append(text)
        elif len(" ".join(self.fallback_parts)) < 280:
            self.fallback_parts.append(text)

    @property
    def title(self) -> str:
        return " ".join(self.title_parts).strip() or "每日简报"

    @property
    def summary(self) -> str:
        value = " ".join(self.summary_parts).strip()
        if not value:
            value = " ".join(self.fallback_parts).strip()
        return value[:220]


def list_briefs() -> list[dict[str, object]]:
    briefs: list[dict[str, object]] = []
    for path in ROOT.glob("20??-??-??.html"):
        match = BRIEF_PATTERN.fullmatch(path.name)
        if not match:
            continue
        parser = BriefMetaParser()
        try:
            parser.feed(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError):
            continue
        briefs.append({
            "date": match.group(1),
            "file": path.name,
            "title": parser.title,
            "summary": parser.summary,
            "items": parser.item_count,
            "modified": datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
        })
    return sorted(briefs, key=lambda item: item["date"], reverse=True)


def safe_file_path(raw_path: str) -> Path | None:
    relative = unquote(raw_path.removeprefix("/files/")).lstrip("/")
    candidate = (ROOT / relative).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError:
        return None
    if BRIEF_PATTERN.fullmatch(relative):
        return candidate
    if relative.startswith("assets/") and candidate.suffix.lower() in {".css", ".webp", ".png", ".jpg", ".jpeg", ".gif", ".svg"}:
        return candidate
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = "DailyBriefReader/1.0"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self.send_bytes(APP_HTML.encode("utf-8"), "text/html; charset=utf-8", no_cache=True)
            return
        if path == "/health":
            payload = json.dumps({"app": APP_ID, "root": str(ROOT)}, ensure_ascii=False).encode("utf-8")
            self.send_bytes(payload, "application/json; charset=utf-8", no_cache=True)
            return
        if path == "/api/briefs":
            payload = json.dumps(list_briefs(), ensure_ascii=False).encode("utf-8")
            self.send_bytes(payload, "application/json; charset=utf-8", no_cache=True)
            return
        if path.startswith("/files/"):
            file_path = safe_file_path(path)
            if not file_path or not file_path.is_file():
                self.send_error(404)
                return
            content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
            data = file_path.read_bytes()
            if file_path.suffix.lower() == ".html":
                text = data.decode("utf-8")
                base = '<base href="/files/" target="_blank">'
                text = text.replace("<head>", "<head>\n  " + base, 1)
                data = text.encode("utf-8")
                content_type = "text/html; charset=utf-8"
            self.send_bytes(data, content_type, no_cache=file_path.suffix.lower() == ".html")
            return
        self.send_error(404)

    def send_bytes(self, data: bytes, content_type: str, *, no_cache: bool = False) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; frame-src 'self'; connect-src 'self'",
        )
        self.send_header("Cache-Control", "no-store" if no_cache else "public, max-age=3600")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format_string: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {format_string % args}")


def existing_server_url() -> str | None:
    try:
        runtime = json.loads(RUNTIME_FILE.read_text(encoding="utf-8"))
        port = int(runtime["port"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None
    url = f"http://127.0.0.1:{port}"
    try:
        with urlopen(url + "/health", timeout=0.7) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("app") == APP_ID and payload.get("root") == str(ROOT):
            return url
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        pass
    return None


def open_browser(url: str) -> None:
    webbrowser.open(url)


def choose_server() -> tuple[ThreadingHTTPServer, int]:
    last_error: OSError | None = None
    for port in range(DEFAULT_PORT, MAX_PORT + 1):
        try:
            return ThreadingHTTPServer(("127.0.0.1", port), Handler), port
        except OSError as exc:
            last_error = exc
    raise OSError(f"No free local port in {DEFAULT_PORT}-{MAX_PORT}") from last_error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--open", action="store_true", help="Open the reader in the default browser")
    args = parser.parse_args()

    existing = existing_server_url()
    if existing:
        if args.open:
            open_browser(existing)
        return 0

    server, port = choose_server()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_FILE.write_text(
        json.dumps({"port": port, "pid": os.getpid(), "root": str(ROOT)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    url = f"http://127.0.0.1:{port}"
    if args.open:
        threading.Timer(0.35, open_browser, args=(url,)).start()

    def stop(_signum: int, _frame: object) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print(f"Daily Brief Reader: {url} (root: {ROOT})")
    try:
        server.serve_forever()
    finally:
        server.server_close()
        try:
            runtime = json.loads(RUNTIME_FILE.read_text(encoding="utf-8"))
            if runtime.get("pid") == os.getpid():
                RUNTIME_FILE.unlink(missing_ok=True)
        except (OSError, json.JSONDecodeError):
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
