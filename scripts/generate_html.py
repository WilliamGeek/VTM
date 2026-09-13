#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_html.py
----------------
将思维导图 Markdown 文件转换为工业级、自包含、高保真交互式单文件 HTML。
核心特性：
1. 双套现代主题系统：Tokyo Night 深色拟态与 Clean Minimal 极简浅色，磨砂玻璃浮动控制坞。
2. 电影级高熵图片灯箱 (Cinema Lightbox)：点击就地放大、平移缩放 (Pan & Zoom)、1:1 还原与单图下载。
3. 全局实时搜索与智能展开：键入关键词即刻高亮命中节点，并自动下钻展开所有深层折叠父分支。
4. 工业级多端导出矩阵：4K 超清 PNG 导出、矢量 SVG 导出、纯前端一键打包标准原生 .xmind 文件、Markdown 下载。
5. 专业级键盘工作流：数字键快捷折叠、全屏专注模式、快捷键速查手册。
6. 100% 独立便携离线支持：支持 --embed-images 将本地相对图片转为 Base64 内嵌。
"""

import os
import sys
import re
import json
import base64
import mimetypes
import argparse
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} - 交互式多模态知识思维导图</title>
  <style>
    :root {{
      --bg-color: #1a1b26;
      --card-bg: rgba(26, 27, 38, 0.85);
      --card-bg-solid: #1a1b26;
      --card-hover: rgba(41, 46, 66, 0.95);
      --border-color: rgba(122, 162, 247, 0.18);
      --border-focus: #7aa2f7;
      --text-color: #c0caf5;
      --text-muted: #7982a9;
      --accent-color: #7aa2f7;
      --accent-gradient: linear-gradient(135deg, #7aa2f7 0%, #bb9af7 100%);
      --accent-hover: #bb9af7;
      --btn-bg: rgba(36, 40, 59, 0.85);
      --btn-hover: rgba(65, 72, 104, 0.9);
      --btn-active: #7aa2f7;
      --highlight-color: #e0af68;
      --highlight-bg: rgba(224, 175, 104, 0.25);
      --shadow-sm: 0 4px 12px rgba(0, 0, 0, 0.25);
      --shadow-md: 0 8px 24px rgba(0, 0, 0, 0.35);
      --shadow-lg: 0 16px 40px rgba(0, 0, 0, 0.5);
    }}
    [data-theme="light"] {{
      --bg-color: #f8fafc;
      --card-bg: rgba(255, 255, 255, 0.9);
      --card-bg-solid: #ffffff;
      --card-hover: rgba(241, 245, 249, 0.98);
      --border-color: rgba(37, 99, 235, 0.15);
      --border-focus: #2563eb;
      --text-color: #0f172a;
      --text-muted: #64748b;
      --accent-color: #2563eb;
      --accent-gradient: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
      --accent-hover: #1d4ed8;
      --btn-bg: rgba(241, 245, 249, 0.9);
      --btn-hover: rgba(226, 232, 240, 1);
      --btn-active: #2563eb;
      --highlight-color: #b45309;
      --highlight-bg: rgba(245, 158, 11, 0.22);
      --shadow-sm: 0 4px 12px rgba(0, 0, 0, 0.06);
      --shadow-md: 0 8px 24px rgba(0, 0, 0, 0.1);
      --shadow-lg: 0 16px 40px rgba(0, 0, 0, 0.15);
    }}
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body, html {{
      width: 100%;
      height: 100%;
      overflow: hidden;
      background-color: var(--bg-color);
      color: var(--text-color);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      transition: background-color 0.3s ease, color 0.3s ease;
      user-select: none;
    }}
    #mindmap-svg {{
      width: 100%;
      height: 100%;
      display: block;
      cursor: grab;
    }}
    #mindmap-svg:active {{
      cursor: grabbing;
    }}

    /* 现代节点样式与高熵图表外壳 */
    .markmap-foreign {{
      user-select: text;
      color: var(--text-color);
    }}
    .markmap-foreign img,
    .markmap-foreign-testing-max img {{
      max-width: 440px !important;
      max-height: 280px !important;
      width: auto !important;
      height: auto !important;
      border-radius: 8px;
      border: 1.5px solid var(--border-color);
      box-shadow: var(--shadow-sm);
      margin: 6px 0;
      display: block;
      cursor: zoom-in;
      transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.25s ease, border-color 0.25s ease;
      background-color: rgba(0, 0, 0, 0.1);
    }}
    .markmap-foreign img:hover,
    .markmap-foreign-testing-max img:hover {{
      transform: translateY(-2px) scale(1.025);
      border-color: var(--accent-color);
      box-shadow: var(--shadow-md);
    }}
    .markmap-foreign table {{
      border-collapse: collapse;
      margin: 8px 0;
      font-size: 12px;
      background: var(--card-bg);
      border-radius: 6px;
      overflow: hidden;
      box-shadow: var(--shadow-sm);
      border: 1px solid var(--border-color);
    }}
    .markmap-foreign th, .markmap-foreign td {{
      border: 1px solid var(--border-color);
      padding: 5px 10px;
      text-align: left;
    }}
    .markmap-foreign th {{
      background: var(--btn-hover);
      color: var(--accent-color);
      font-weight: 600;
      letter-spacing: 0.3px;
    }}
    .markmap-foreign tr:nth-child(even) {{
      background: rgba(122, 162, 247, 0.04);
    }}

    /* 搜索：所有匹配字符的内联高亮（温暖琥珀色底色） */
    .markmap-foreign mark.search-hit {{
      background: rgba(245, 158, 11, 0.25);
      color: #f59e0b;
      font-weight: 700;
      border-radius: 2px;
      padding: 0 1px;
      border-bottom: 2px solid rgba(245, 158, 11, 0.5);
      transition: background 0.2s, box-shadow 0.2s;
    }}
    [data-theme="light"] .markmap-foreign mark.search-hit {{
      background: rgba(245, 158, 11, 0.18);
      color: #b45309;
      border-bottom-color: rgba(180, 83, 9, 0.5);
    }}
    /* 当前聚焦的匹配字符：强化脉冲发光 */
    .markmap-foreign mark.search-hit.search-current {{
      background: rgba(239, 68, 68, 0.35);
      color: #ef4444;
      border-bottom: 2px solid #ef4444;
      box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.3), 0 0 8px rgba(239, 68, 68, 0.25);
      animation: pulse-hit 1.2s infinite alternate;
    }}
    [data-theme="light"] .markmap-foreign mark.search-hit.search-current {{
      background: rgba(220, 38, 38, 0.18);
      color: #dc2626;
      border-bottom-color: #dc2626;
      box-shadow: 0 0 0 2px rgba(220, 38, 38, 0.25), 0 0 8px rgba(220, 38, 38, 0.15);
    }}
    @keyframes pulse-hit {{
      0% {{ box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.3), 0 0 8px rgba(239, 68, 68, 0.25); }}
      100% {{ box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.15), 0 0 12px rgba(239, 68, 68, 0.1); }}
    }}

    /* 顶部磨砂玻璃浮动控制坞 (Floating Pill Dock) */
    .dock-container {{
      position: absolute;
      top: 18px;
      left: 50%;
      transform: translateX(-50%);
      display: flex;
      align-items: center;
      gap: 10px;
      z-index: 1000;
      pointer-events: auto;
    }}
    .dock-pill {{
      display: flex;
      align-items: center;
      gap: 6px;
      background: var(--card-bg);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      padding: 6px 10px;
      border-radius: 24px;
      border: 1px solid var(--border-color);
      box-shadow: var(--shadow-md);
      transition: box-shadow 0.25s, border-color 0.25s;
    }}
    .dock-pill:hover {{
      border-color: rgba(122, 162, 247, 0.35);
      box-shadow: var(--shadow-lg);
    }}

    /* 搜索栏组件 */
    .search-box {{
      display: flex;
      align-items: center;
      background: var(--btn-bg);
      border: 1px solid var(--border-color);
      border-radius: 16px;
      padding: 4px 10px;
      transition: all 0.25s ease;
      width: 175px;
    }}
    .search-box:focus-within {{
      width: 240px;
      border-color: var(--border-focus);
      box-shadow: 0 0 0 3px rgba(122, 162, 247, 0.2);
      background: var(--card-bg-solid);
    }}
    .search-box input {{
      border: none;
      background: transparent;
      color: var(--text-color);
      font-size: 12.5px;
      outline: none;
      width: 100%;
      margin-left: 6px;
    }}
    .search-box input::placeholder {{
      color: var(--text-muted);
    }}
    .search-count {{
      font-size: 11px;
      color: var(--text-muted);
      margin-left: 4px;
      white-space: nowrap;
    }}
    .search-nav-btn {{
      background: transparent;
      border: none;
      color: var(--text-muted);
      cursor: pointer;
      padding: 2px 4px;
      border-radius: 4px;
      font-size: 11px;
      display: none;
    }}
    .search-nav-btn:hover {{
      color: var(--accent-color);
      background: var(--btn-hover);
    }}

    /* 缩放控制器模块 */
    .zoom-group {{
      display: inline-flex;
      align-items: center;
      background: var(--btn-bg);
      border: 1px solid var(--border-color);
      border-radius: 16px;
      padding: 1px;
      gap: 1px;
      transition: all 0.2s ease;
    }}
    .zoom-group:hover {{
      border-color: rgba(122, 162, 247, 0.4);
    }}
    .zoom-btn {{
      background: transparent;
      border: none;
      color: var(--text-muted);
      width: 22px;
      height: 22px;
      border-radius: 11px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 13px;
      font-weight: bold;
      transition: all 0.15s ease;
      user-select: none;
      padding: 0;
    }}
    .zoom-btn:hover {{
      background: var(--btn-hover);
      color: var(--accent-color);
    }}
    .zoom-indicator {{
      min-width: 46px;
      padding: 0 4px;
      font-size: 11px;
      font-weight: 600;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-variant-numeric: tabular-nums;
      color: var(--text-color);
      text-align: center;
      cursor: pointer;
      user-select: none;
      border: none;
      background: transparent;
      border-radius: 8px;
      height: 22px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      transition: all 0.15s ease;
    }}
    .zoom-indicator:hover {{
      background: var(--btn-hover);
      color: var(--accent-color);
    }}
    .dock-divider {{
      width: 1px;
      height: 14px;
      background: var(--border-color);
      margin: 0 2px;
    }}

    /* 按钮组 */
    .dock-btn {{
      background: var(--btn-bg);
      border: 1px solid var(--border-color);
      color: var(--text-color);
      padding: 6px 11px;
      border-radius: 16px;
      cursor: pointer;
      font-size: 12.5px;
      font-weight: 500;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      transition: all 0.2s ease;
      white-space: nowrap;
    }}
    .dock-btn:hover {{
      background: var(--btn-hover);
      border-color: var(--accent-color);
      color: var(--accent-color);
      transform: translateY(-1px);
    }}
    .dock-btn:active {{
      transform: translateY(0);
    }}
    .dock-btn svg {{
      width: 14px;
      height: 14px;
      fill: currentColor;
    }}

    /* 下拉菜单 (导出菜单) */
    .dropdown {{
      position: relative;
      display: inline-block;
    }}
    .dropdown-content {{
      display: none;
      position: absolute;
      top: calc(100% + 8px);
      right: 0;
      background: var(--card-bg-solid);
      backdrop-filter: blur(14px);
      min-width: 175px;
      box-shadow: var(--shadow-lg);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 6px;
      z-index: 1010;
      flex-direction: column;
      gap: 3px;
      animation: fadeIn 0.15s ease-out;
    }}
    .dropdown.active .dropdown-content {{
      display: flex;
    }}
    .dropdown-item {{
      background: transparent;
      border: none;
      color: var(--text-color);
      padding: 8px 12px;
      border-radius: 8px;
      text-align: left;
      font-size: 12.5px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      transition: background 0.15s;
    }}
    .dropdown-item:hover {{
      background: var(--btn-hover);
      color: var(--accent-color);
    }}

    /* 左下角信息徽章 */
    .status-badge {{
      position: absolute;
      bottom: 16px;
      left: 18px;
      background: var(--card-bg);
      backdrop-filter: blur(14px);
      padding: 8px 14px;
      border-radius: 20px;
      border: 1px solid var(--border-color);
      box-shadow: var(--shadow-sm);
      font-size: 12px;
      color: var(--text-muted);
      z-index: 100;
      display: flex;
      align-items: center;
      gap: 8px;
      max-width: 480px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .status-badge strong {{
      color: var(--text-color);
      font-weight: 600;
    }}
    .status-badge .indicator {{
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #10b981;
      box-shadow: 0 0 8px #10b981;
      flex-shrink: 0;
    }}

    /* 快捷键提示按钮 (右下角) */
    .help-btn {{
      position: absolute;
      bottom: 16px;
      right: 18px;
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: var(--card-bg);
      backdrop-filter: blur(14px);
      border: 1px solid var(--border-color);
      color: var(--text-muted);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      box-shadow: var(--shadow-sm);
      font-size: 14px;
      font-weight: bold;
      transition: all 0.2s;
      z-index: 100;
    }}
    .help-btn:hover {{
      color: var(--accent-color);
      border-color: var(--accent-color);
      transform: scale(1.08);
    }}

    /* 电影级图片灯箱 (Cinema Lightbox Modal) */
    .lightbox-modal {{
      display: none;
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(10, 12, 18, 0.88);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      z-index: 2000;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      opacity: 0;
      transition: opacity 0.25s ease;
    }}
    .lightbox-modal.active {{
      display: flex;
      opacity: 1;
    }}
    .lightbox-viewport {{
      flex: 1;
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
      position: relative;
      cursor: grab;
    }}
    .lightbox-viewport:active {{
      cursor: grabbing;
    }}
    .lightbox-img {{
      max-width: 90vw;
      max-height: 82vh;
      object-fit: contain;
      border-radius: 8px;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6);
      transition: transform 0.1s ease-out;
      transform-origin: center center;
      user-select: none;
    }}
    .lightbox-dock {{
      display: flex;
      align-items: center;
      gap: 12px;
      background: var(--card-bg);
      backdrop-filter: blur(14px);
      padding: 8px 18px;
      border-radius: 28px;
      border: 1px solid var(--border-color);
      margin-bottom: 24px;
      box-shadow: var(--shadow-lg);
      color: var(--text-color);
      font-size: 13px;
    }}
    .lightbox-dock button {{
      background: var(--btn-bg);
      border: 1px solid var(--border-color);
      color: var(--text-color);
      width: 32px;
      height: 32px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      font-size: 14px;
      transition: all 0.15s;
    }}
    .lightbox-dock button:hover {{
      background: var(--btn-hover);
      color: var(--accent-color);
      border-color: var(--accent-color);
    }}
    .lightbox-dock .caption {{
      max-width: 320px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      font-weight: 500;
      color: var(--text-color);
      margin-right: 8px;
    }}

    /* 快捷键速查模态框 */
    .shortcuts-modal {{
      display: none;
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.6);
      backdrop-filter: blur(8px);
      z-index: 2000;
      align-items: center;
      justify-content: center;
    }}
    .shortcuts-modal.active {{
      display: flex;
    }}
    .shortcuts-card {{
      background: var(--card-bg-solid);
      border: 1px solid var(--border-color);
      border-radius: 16px;
      padding: 24px;
      width: 440px;
      max-width: 90vw;
      box-shadow: var(--shadow-lg);
    }}
    .shortcuts-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }}
    .shortcuts-header h3 {{
      font-size: 16px;
      color: var(--accent-color);
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .shortcuts-list {{
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .shortcut-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 13px;
    }}
    .shortcut-keys {{
      display: flex;
      gap: 4px;
    }}
    .kbd {{
      background: var(--btn-bg);
      border: 1px solid var(--border-color);
      padding: 2px 7px;
      border-radius: 5px;
      font-size: 11px;
      font-family: monospace;
      color: var(--accent-color);
      box-shadow: 0 2px 0 rgba(0,0,0,0.2);
    }}

    @keyframes fadeIn {{
      from {{ opacity: 0; transform: translateY(-6px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
  </style>

  <!-- 外部基础引擎与客户端离线打包套件 -->
  <!-- VENDOR_SCRIPTS_PLACEHOLDER -->
</head>
<body>

  <!-- 顶部磨砂玻璃控制坞 -->
  <div class="dock-container">
    <!-- 搜索过滤 Pill -->
    <div class="dock-pill">
      <div class="search-box">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="var(--text-muted)"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
        <input type="text" id="search-input" placeholder="搜索导图 (按 / 聚焦)..." autocomplete="off" />
        <span class="search-count" id="search-count"></span>
        <button class="search-nav-btn" id="search-prev" title="上一个 (Shift+Enter)">▲</button>
        <button class="search-nav-btn" id="search-next" title="下一个 (Enter)">▼</button>
      </div>
    </div>

    <!-- 视图控制 Pill -->
    <div class="dock-pill">
      <!-- 画布缩放控制块 -->
      <div class="zoom-group">
        <button class="zoom-btn" id="btn-zoom-out" title="缩小画布 (-)">−</button>
        <button class="zoom-indicator" id="zoom-indicator" title="当前画布缩放比例 (点击复位 100% / 适应)">
          <span id="zoom-text">100%</span>
        </button>
        <button class="zoom-btn" id="btn-zoom-in" title="放大画布 (+)">+</button>
      </div>

      <div class="dock-divider"></div>

      <button class="dock-btn" id="btn-fit" title="居中适应画布 (Space)">
        <span>🔍</span> 适应
      </button>
      <div class="dock-divider"></div>
      <button class="dock-btn" id="btn-fold-1" title="收起至一级分支 (快捷键 1)">
        <span>1级</span>
      </button>
      <button class="dock-btn" id="btn-fold-2" title="收起至二级分支 (快捷键 2)">
        <span>2级</span>
      </button>
      <button class="dock-btn" id="btn-fold-3" title="收起至三级分支 (快捷键 3)">
        <span>3级</span>
      </button>
      <button class="dock-btn" id="btn-expand" title="全部展开 (快捷键 0)">
        <span>📂 展开</span>
      </button>
    </div>

    <!-- 模式与导出 Pill -->
    <div class="dock-pill">
      <button class="dock-btn" id="btn-theme" title="切换深浅主题 (T)">
        <span id="theme-icon">🌓</span>
      </button>
      <button class="dock-btn" id="btn-fullscreen" title="全屏演示 (F)">
        <span>⛶</span>
      </button>
      
      <!-- 导出下拉菜单 -->
      <div class="dropdown" id="export-dropdown">
        <button class="dock-btn" id="btn-export-menu" title="导出多格式产物">
          <span>📤 导出 ▾</span>
        </button>
        <div class="dropdown-content">
          <button class="dropdown-item" id="export-xmind">
            <span>🧠</span> 导出原生 .xmind
          </button>
          <button class="dropdown-item" id="export-png">
            <span>📸</span> 导出超清 PNG
          </button>
          <button class="dropdown-item" id="export-svg">
            <span>📐</span> 导出矢量 SVG
          </button>
          <button class="dropdown-item" id="export-markdown">
            <span>📝</span> 下载 Markdown
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- 左下角状态徽章 -->
  <div class="status-badge">
    <div class="indicator"></div>
    <strong>{title}</strong>
    <span>| 视频思维导图</span>
  </div>

  <!-- 右下角帮助按钮 -->
  <div class="help-btn" id="btn-help" title="快捷键速查 (?)">?</div>

  <!-- 思维导图核心 SVG 画布 -->
  <svg id="mindmap-svg"></svg>

  <!-- 电影级图片灯箱模态框 (Cinema Lightbox) -->
  <div class="lightbox-modal" id="lightbox">
    <div class="lightbox-viewport" id="lightbox-viewport">
      <img src="" alt="" class="lightbox-img" id="lightbox-img" />
    </div>
    <div class="lightbox-dock">
      <span class="caption" id="lightbox-caption">图片预览</span>
      <span id="lightbox-scale">100%</span>
      <button id="lightbox-zoom-in" title="放大 (+)">+</button>
      <button id="lightbox-zoom-out" title="缩小 (-)">-</button>
      <button id="lightbox-reset" title="复位 (双击)">↺</button>
      <button id="lightbox-download" title="下载原图">💾</button>
      <button id="lightbox-close" title="关闭 (Esc)">✕</button>
    </div>
  </div>

  <!-- 快捷键速查对话框 -->
  <div class="shortcuts-modal" id="shortcuts-modal">
    <div class="shortcuts-card">
      <div class="shortcuts-header">
        <h3>⌨ 键盘工作流速查</h3>
        <button style="background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:16px;" id="shortcuts-close">✕</button>
      </div>
      <div class="shortcuts-list">
        <div class="shortcut-row">
          <span>聚焦搜索框</span>
          <div class="shortcut-keys"><span class="kbd">/</span> 或 <span class="kbd">Ctrl+F</span></div>
        </div>
        <div class="shortcut-row">
          <span>下一个 / 上一个搜索结果</span>
          <div class="shortcut-keys"><span class="kbd">Enter</span> / <span class="kbd">Shift+Enter</span></div>
        </div>
        <div class="shortcut-row">
          <span>快速折叠至 1 / 2 / 3 级</span>
          <div class="shortcut-keys"><span class="kbd">1</span> / <span class="kbd">2</span> / <span class="kbd">3</span></div>
        </div>
        <div class="shortcut-row">
          <span>展开全部分支</span>
          <div class="shortcut-keys"><span class="kbd">0</span></div>
        </div>
        <div class="shortcut-row">
          <span>放大 / 缩小画布</span>
          <div class="shortcut-keys"><span class="kbd">+</span> / <span class="kbd">-</span></div>
        </div>
        <div class="shortcut-row">
          <span>居中适应画布</span>
          <div class="shortcut-keys"><span class="kbd">Space</span></div>
        </div>
        <div class="shortcut-row">
          <span>切换深浅主题</span>
          <div class="shortcut-keys"><span class="kbd">T</span></div>
        </div>
        <div class="shortcut-row">
          <span>切换全屏模式</span>
          <div class="shortcut-keys"><span class="kbd">F</span></div>
        </div>
        <div class="shortcut-row">
          <span>关闭所有弹窗 / 灯箱</span>
          <div class="shortcut-keys"><span class="kbd">Esc</span></div>
        </div>
        <div class="shortcut-row">
          <span>打开本帮助手册</span>
          <div class="shortcut-keys"><span class="kbd">?</span></div>
        </div>
      </div>
    </div>
  </div>

  <script>
    const markdownContent = {markdown_json};
    const documentTitle = {title_json};

    window.addEventListener('DOMContentLoaded', () => {{
      const {{ Transformer, Markmap, loadCSS, loadJS }} = window.markmap;
      const transformer = new Transformer();
      const {{ root, features }} = transformer.transform(markdownContent);
      const {{ styles, scripts }} = transformer.getUsedAssets(features);

      if (styles) loadCSS(styles);
      if (scripts) loadJS(scripts);

      // 拦截 Markmap 原生图片加载与测量逻辑：
      // 等比自适应缩放至 max-width: 440px / max-height: 280px 约束范围，
      // 彻底消除原始高分辨率图片导致 foreignObject 产生巨大空白间隙的问题
      const MAX_IMG_W = 440;
      const MAX_IMG_H = 280;
      Markmap.prototype._loadImage = function(src) {{
        this.imgCache[src] = [0, 0];
        const img = new Image();
        img.src = src;
        img.onload = () => {{
          let w = img.naturalWidth;
          let h = img.naturalHeight;
          if (w > MAX_IMG_W || h > MAX_IMG_H) {{
            const ratio = Math.min(MAX_IMG_W / w, MAX_IMG_H / h);
            w = Math.round(w * ratio);
            h = Math.round(h * ratio);
          }}
          this.imgCache[src] = [w, h];
          this.debouncedRefresh();
        }};
      }};

      Markmap.prototype._checkImages = function(container) {{
        container.querySelectorAll('img').forEach((img) => {{
          const cached = this.imgCache[img.src];
          if (cached && cached[0]) {{
            [img.width, img.height] = cached;
          }} else if (!cached) {{
            this._loadImage(img.src);
          }}
        }});
      }};

      const svgEl = document.getElementById('mindmap-svg');
      const mm = Markmap.create(svgEl, {{
        duration: 350,
        nodeMinHeight: 20,
        spacingVertical: 10,
        spacingHorizontal: 85,
        paddingX: 18,
        autoFit: true
      }}, root);

      // ==================== 1. 层级折叠控制 ====================
      function setFoldLevel(node, targetLevel, curLevel = 0) {{
        if (!node.children || node.children.length === 0) return;
        if (curLevel >= targetLevel) {{
          node.payload = node.payload || {{}};
          node.payload.fold = 1;
        }} else {{
          if (node.payload) node.payload.fold = 0;
        }}
        node.children.forEach(child => setFoldLevel(child, targetLevel, curLevel + 1));
      }}

      // 缩放比例指示与控制
      const zoomText = document.getElementById('zoom-text');
      const zoomIndicator = document.getElementById('zoom-indicator');
      const btnZoomIn = document.getElementById('btn-zoom-in');
      const btnZoomOut = document.getElementById('btn-zoom-out');

      function updateZoomDisplay(k) {{
        if (!zoomText) return;
        const scaleVal = (k !== undefined && k !== null) ? k : d3.zoomTransform(svgEl).k;
        zoomText.textContent = Math.round(scaleVal * 100) + '%';
      }}

      // 实时监听 D3 画布缩放与平移事件
      mm.zoom.on('zoom.indicator', (e) => {{
        if (e && e.transform) updateZoomDisplay(e.transform.k);
      }});

      // 通过 MutationObserver 捕获所有 transform 属性变动
      if (mm.g && mm.g.node()) {{
        const zoomObserver = new MutationObserver(() => {{
          const t = d3.zoomTransform(svgEl);
          updateZoomDisplay(t.k);
        }});
        zoomObserver.observe(mm.g.node(), {{ attributes: true, attributeFilter: ['transform'] }});
      }}

      btnZoomIn.addEventListener('click', () => mm.rescale(1.25));
      btnZoomOut.addEventListener('click', () => mm.rescale(0.8));
      zoomIndicator.addEventListener('click', () => {{
        const curK = d3.zoomTransform(svgEl).k;
        if (Math.abs(curK - 1.0) < 0.04) {{
          mm.fit();
        }} else {{
          mm.rescale(1.0 / curK);
        }}
      }});

      setTimeout(() => updateZoomDisplay(), 300);

      document.getElementById('btn-fit').addEventListener('click', () => mm.fit());
      document.getElementById('btn-fold-1').addEventListener('click', () => {{
        setFoldLevel(root, 1);
        mm.renderData(root);
        mm.fit();
      }});
      document.getElementById('btn-fold-2').addEventListener('click', () => {{
        setFoldLevel(root, 2);
        mm.renderData(root);
        mm.fit();
      }});
      document.getElementById('btn-fold-3').addEventListener('click', () => {{
        setFoldLevel(root, 3);
        mm.renderData(root);
        mm.fit();
      }});
      document.getElementById('btn-expand').addEventListener('click', () => {{
        setFoldLevel(root, 999);
        mm.renderData(root);
        mm.fit();
      }});

      // ==================== 2. 主题切换与全屏 ====================
      const btnTheme = document.getElementById('btn-theme');
      btnTheme.addEventListener('click', () => toggleTheme());
      function toggleTheme() {{
        const curTheme = document.documentElement.getAttribute('data-theme');
        const nextTheme = curTheme === 'light' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', nextTheme);
        document.getElementById('theme-icon').textContent = nextTheme === 'light' ? '☀️' : '🌓';
      }}

      const btnFullscreen = document.getElementById('btn-fullscreen');
      btnFullscreen.addEventListener('click', () => toggleFullscreen());
      function toggleFullscreen() {{
        if (!document.fullscreenElement) {{
          document.documentElement.requestFullscreen().catch(() => {{}});
        }} else {{
          if (document.exitFullscreen) document.exitFullscreen();
        }}
      }}

      // ==================== 3. 电影级图片灯箱 (Cinema Lightbox) ====================
      const lightbox = document.getElementById('lightbox');
      const lightboxImg = document.getElementById('lightbox-img');
      const lightboxCaption = document.getElementById('lightbox-caption');
      const lightboxScale = document.getElementById('lightbox-scale');
      let currentScale = 1.0;
      let panX = 0, panY = 0;
      let isDragging = false;
      let startX = 0, startY = 0;

      function updateLightboxTransform() {{
        lightboxImg.style.transform = `translate(${{panX}}px, ${{panY}}px) scale(${{currentScale}})`;
        lightboxScale.textContent = Math.round(currentScale * 100) + '%';
      }}

      function resetLightbox() {{
        currentScale = 1.0;
        panX = 0;
        panY = 0;
        updateLightboxTransform();
      }}

      // 代理导图中所有图片的点击事件
      document.addEventListener('click', (e) => {{
        const target = e.target;
        if (target.tagName === 'IMG' && target.closest('.markmap-foreign')) {{
          e.stopPropagation();
          lightboxImg.src = target.src;
          lightboxCaption.textContent = target.alt || target.title || '架构图表与关键帧';
          resetLightbox();
          lightbox.classList.add('active');
        }}
      }});

      document.getElementById('lightbox-zoom-in').addEventListener('click', () => {{
        currentScale = Math.min(currentScale + 0.25, 4.0);
        updateLightboxTransform();
      }});
      document.getElementById('lightbox-zoom-out').addEventListener('click', () => {{
        currentScale = Math.max(currentScale - 0.25, 0.4);
        updateLightboxTransform();
      }});
      document.getElementById('lightbox-reset').addEventListener('click', () => resetLightbox());
      document.getElementById('lightbox-close').addEventListener('click', () => {{
        lightbox.classList.remove('active');
      }});

      // 滚轮缩放
      document.getElementById('lightbox-viewport').addEventListener('wheel', (e) => {{
        e.preventDefault();
        const delta = e.deltaY < 0 ? 0.15 : -0.15;
        currentScale = Math.max(0.3, Math.min(5.0, currentScale + delta));
        updateLightboxTransform();
      }}, {{ passive: false }});

      // 拖拽平移
      const viewport = document.getElementById('lightbox-viewport');
      viewport.addEventListener('mousedown', (e) => {{
        if (e.target === lightboxImg || e.target === viewport) {{
          isDragging = true;
          startX = e.clientX - panX;
          startY = e.clientY - panY;
        }}
      }});
      window.addEventListener('mousemove', (e) => {{
        if (isDragging) {{
          panX = e.clientX - startX;
          panY = e.clientY - startY;
          updateLightboxTransform();
        }}
      }});
      window.addEventListener('mouseup', () => isDragging = false);

      // 下载当前灯箱图片
      document.getElementById('lightbox-download').addEventListener('click', () => {{
        const a = document.createElement('a');
        a.href = lightboxImg.src;
        a.download = (lightboxCaption.textContent || 'mindmap_figure') + '.png';
        a.click();
      }});

      // ==================== 4. 全局实时搜索与智能下钻 ====================
      const searchInput = document.getElementById('search-input');
      const searchCount = document.getElementById('search-count');
      const searchPrev = document.getElementById('search-prev');
      const searchNext = document.getElementById('search-next');
      let matchedMarks = [];       // 所有命中的 <mark> 元素列表（逐字粒度）
      let currentMatchIdx = -1;
      let activeQuery = '';
      let searchTimer = null;

      // -- 清理：移除所有内联 <mark> 和聚焦样式 --
      function clearSearchHighlight() {{
        document.querySelectorAll('mark.search-hit').forEach(mark => {{
          const parent = mark.parentNode;
          if (parent) {{
            parent.replaceChild(document.createTextNode(mark.textContent), mark);
            parent.normalize();
          }}
        }});
      }}

      // -- 递归展开数据树中匹配节点的所有折叠祖先 --
      function expandMatchedAncestors(node, query, ancestors = []) {{
        if (!node) return;
        const text = node.content ? node.content.replace(/<[^>]+>/g, '') : '';
        const currentPath = [...ancestors, node];
        if (text.toLowerCase().includes(query.toLowerCase())) {{
          // 展开此节点的全部祖先
          currentPath.forEach(anc => {{
            anc.payload = anc.payload || {{}};
            anc.payload.fold = 0;
          }});
        }}
        if (node.children) {{
          node.children.forEach(child => expandMatchedAncestors(child, query, currentPath));
        }}
      }}

      // -- 在 DOM 文本节点中注入 <mark> 高亮 --
      function injectInlineHighlights(container, query) {{
        if (!query) return;
        const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
        const textNodes = [];
        while (walker.nextNode()) textNodes.push(walker.currentNode);

        const lowerQ = query.toLowerCase();
        for (const textNode of textNodes) {{
          const text = textNode.textContent;
          const lowerText = text.toLowerCase();
          if (!lowerText.includes(lowerQ)) continue;

          const frag = document.createDocumentFragment();
          let lastIdx = 0;
          let searchIdx = 0;
          while ((searchIdx = lowerText.indexOf(lowerQ, lastIdx)) !== -1) {{
            if (searchIdx > lastIdx) {{
              frag.appendChild(document.createTextNode(text.slice(lastIdx, searchIdx)));
            }}
            const mark = document.createElement('mark');
            mark.className = 'search-hit';
            mark.textContent = text.slice(searchIdx, searchIdx + query.length);
            frag.appendChild(mark);
            lastIdx = searchIdx + query.length;
          }}
          if (lastIdx < text.length) {{
            frag.appendChild(document.createTextNode(text.slice(lastIdx)));
          }}
          textNode.parentNode.replaceChild(frag, textNode);
        }}
      }}

      // -- 计算元素在导图 SVG 画布本地坐标系中的坐标 (x, y) --
      function getMarkCanvasPoint(el) {{
        const rect = el.getBoundingClientRect();
        const pt = svgEl.createSVGPoint();
        pt.x = rect.left + rect.width / 2;
        pt.y = rect.top + rect.height / 2;
        const gNode = mm.g ? mm.g.node() : null;
        if (gNode) {{
          try {{
            const ctm = gNode.getScreenCTM();
            if (ctm) {{
              const local = pt.matrixTransform(ctm.inverse());
              return {{ x: local.x, y: local.y }};
            }}
          }} catch (e) {{}}
        }}
        return {{ x: pt.x, y: pt.y }};
      }}

      // -- 主搜索执行 --
      function executeSearch(query) {{
        if (searchTimer) clearTimeout(searchTimer);
        clearSearchHighlight();
        matchedMarks = [];
        currentMatchIdx = -1;
        activeQuery = query.trim();

        if (!activeQuery) {{
          searchCount.textContent = '';
          searchPrev.style.display = 'none';
          searchNext.style.display = 'none';
          return;
        }}

        // 1. 在数据树中展开匹配节点的折叠祖先并渲染
        expandMatchedAncestors(root, activeQuery);
        mm.renderData(root);

        // 2. 等待展开重排动画完成后，在 DOM 层注入 <mark> 高亮并严格按视觉从上到下、同行从左到右排序
        searchTimer = setTimeout(() => {{
          const allForeign = document.querySelectorAll('.markmap-foreign');
          const lowerQ = activeQuery.toLowerCase();

          allForeign.forEach(el => {{
            const plainText = el.textContent.toLowerCase();
            if (plainText.includes(lowerQ)) {{
              injectInlineHighlights(el, activeQuery);
            }}
          }});

          // 收集所有 <mark.search-hit>
          const rawMarks = Array.from(document.querySelectorAll('mark.search-hit'));
          if (rawMarks.length === 0) {{
            searchCount.textContent = '(0)';
            searchPrev.style.display = 'none';
            searchNext.style.display = 'none';
            return;
          }}

          // 计算每个命中标记在导图画布坐标系下的几何中心
          const items = rawMarks.map(mark => ({{
            mark,
            pt: getMarkCanvasPoint(mark)
          }}));

          // 严格按视觉“从上到下，同行从左到右”排序
          items.sort((a, b) => {{
            if (Math.abs(a.pt.y - b.pt.y) > 14) {{
              return a.pt.y - b.pt.y;
            }}
            return a.pt.x - b.pt.x;
          }});

          matchedMarks = items.map(item => item.mark);

          const total = matchedMarks.length;
          searchCount.textContent = total ? `(1/${{total}})` : '(0)';
          searchPrev.style.display = total > 1 ? 'inline-block' : 'none';
          searchNext.style.display = total > 1 ? 'inline-block' : 'none';

          if (total > 0) focusMatch(0);
        }}, 380);
      }}

      // -- 聚焦第 N 个匹配的 <mark> 元素 --
      function focusMatch(index) {{
        if (matchedMarks.length === 0) return;
        // 移除上一个聚焦标记
        document.querySelectorAll('mark.search-current').forEach(el => el.classList.remove('search-current'));

        currentMatchIdx = (index + matchedMarks.length) % matchedMarks.length;
        searchCount.textContent = `(${{currentMatchIdx + 1}}/${{matchedMarks.length}})`;

        const target = matchedMarks[currentMatchIdx];
        target.classList.add('search-current');

        // 计算目标在 SVG 画布中的坐标并平滑自动转换视角与自适应适度缩放
        try {{
          const svgRect = svgEl.getBoundingClientRect();
          const targetPt = getMarkCanvasPoint(target);

          // 视口居中目标坐标
          const viewCenterX = svgRect.width / 2;
          const viewCenterY = svgRect.height / 2;

          // 智能自适应聚焦缩放比例：
          // 若当前缩放过远 (< 1.15)，适度放大至舒适阅读比例 1.25；
          // 若当前缩放过大 (> 2.0)，适度调整至 1.55 呈现上下文；
          // 若在舒适区间内，保持用户当前的缩放喜好
          const currentK = d3.zoomTransform(svgEl).k;
          let targetK = currentK;
          if (currentK < 1.15) {{
            targetK = 1.25;
          }} else if (currentK > 2.0) {{
            targetK = 1.55;
          }}

          const newX = viewCenterX - targetPt.x * targetK;
          const newY = viewCenterY - targetPt.y * targetK;
          const newTransform = d3.zoomIdentity.translate(newX, newY).scale(targetK);

          d3.select(svgEl)
            .transition()
            .duration(500)
            .ease(d3.easeCubicOut)
            .call(mm.zoom.transform, newTransform);
        }} catch (err) {{
          target.scrollIntoView({{ behavior: 'smooth', block: 'center', inline: 'center' }});
        }}
      }}

      searchInput.addEventListener('input', (e) => executeSearch(e.target.value));
      searchNext.addEventListener('click', () => focusMatch(currentMatchIdx + 1));
      searchPrev.addEventListener('click', () => focusMatch(currentMatchIdx - 1));
      searchInput.addEventListener('keydown', (e) => {{
        if (e.key === 'Enter') {{
          if (e.shiftKey) focusMatch(currentMatchIdx - 1);
          else focusMatch(currentMatchIdx + 1);
        }}
      }});

      // ==================== 5. 工业级多格式导出矩阵 ====================
      const exportDropdown = document.getElementById('export-dropdown');
      const btnExportMenu = document.getElementById('btn-export-menu');
      btnExportMenu.addEventListener('click', (e) => {{
        e.stopPropagation();
        exportDropdown.classList.toggle('active');
      }});
      document.addEventListener('click', () => exportDropdown.classList.remove('active'));

      // 5.1 导出标准原生 .xmind (基于 JSZip 实时打包)
      document.getElementById('export-xmind').addEventListener('click', () => {{
        exportDropdown.classList.remove('active');
        try {{
          function stripHtml(html) {{
            const tmp = document.createElement('div');
            tmp.innerHTML = html || '';
            return tmp.textContent || tmp.innerText || '';
          }}

          function convertAstToXMindTopic(astNode, isRoot = false) {{
            const rawTitle = stripHtml(astNode.content).trim() || (isRoot ? documentTitle : '主题');
            const topic = {{
              id: 'topic_' + Math.random().toString(36).substr(2, 9),
              title: rawTitle
            }};
            if (isRoot) {{
              topic.class = 'topic';
              topic.structureClass = 'org.xmind.ui.map.unbalanced';
            }}
            if (astNode.children && astNode.children.length > 0) {{
              topic.children = {{
                attached: astNode.children.map(child => convertAstToXMindTopic(child, false))
              }};
            }}
            return topic;
          }}

          const xmindContent = [{{
            id: 'sheet_' + Math.random().toString(36).substr(2, 9),
            class: 'sheet',
            title: '画布 1',
            rootTopic: convertAstToXMindTopic(root, true)
          }}];

          const metadata = {{
            creator: {{
              name: "video-to-mindmap"
            }}
          }};

          const manifest = {{
            "file-entries": {{
              "content.json": {{}},
              "metadata.json": {{}}
            }}
          }};

          const zip = new JSZip();
          zip.file("content.json", JSON.stringify(xmindContent, null, 2));
          zip.file("metadata.json", JSON.stringify(metadata, null, 2));
          zip.file("manifest.json", JSON.stringify(manifest, null, 2));

          zip.generateAsync({{ type: "blob" }}).then(blob => {{
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `${{documentTitle}}.xmind`;
            a.click();
            URL.revokeObjectURL(a.href);
          }});
        }} catch (err) {{
          alert('导出 XMind 失败: ' + err.message);
        }}
      }});

      // 5.2 导出矢量 SVG
      document.getElementById('export-svg').addEventListener('click', () => {{
        exportDropdown.classList.remove('active');
        const svgClone = svgEl.cloneNode(true);
        svgClone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
        const blob = new Blob([svgClone.outerHTML], {{ type: 'image/svg+xml;charset=utf-8' }});
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `${{documentTitle}}.svg`;
        a.click();
        URL.revokeObjectURL(a.href);
      }});

      // 5.3 导出 4K 超清 PNG (基于 Canvas)
      document.getElementById('export-png').addEventListener('click', () => {{
        exportDropdown.classList.remove('active');
        const svgData = new XMLSerializer().serializeToString(svgEl);
        const svgBlob = new Blob([svgData], {{ type: 'image/svg+xml;charset=utf-8' }});
        const URLObj = window.URL || window.webkitURL || window;
        const blobURL = URLObj.createObjectURL(svgBlob);
        
        const img = new Image();
        img.onload = function() {{
          const canvas = document.createElement('canvas');
          const scale = 2.5; // 高清比例
          canvas.width = svgEl.clientWidth * scale;
          canvas.height = svgEl.clientHeight * scale;
          const ctx = canvas.getContext('2d');
          
          // 绘制当前主题背景色
          const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
          ctx.fillStyle = isDark ? '#1a1b26' : '#f8fafc';
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

          canvas.toBlob(pngBlob => {{
            if (pngBlob) {{
              const a = document.createElement('a');
              a.href = URLObj.createObjectURL(pngBlob);
              a.download = `${{documentTitle}}_4K.png`;
              a.click();
            }}
          }}, 'image/png');
        }};
        img.src = blobURL;
      }});

      // 5.4 下载原始 Markdown
      document.getElementById('export-markdown').addEventListener('click', () => {{
        exportDropdown.classList.remove('active');
        const blob = new Blob([markdownContent], {{ type: 'text/markdown;charset=utf-8' }});
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `${{documentTitle}}_mindmap.md`;
        a.click();
        URL.revokeObjectURL(a.href);
      }});

      // ==================== 6. 快捷键速查模态框 ====================
      const shortcutsModal = document.getElementById('shortcuts-modal');
      document.getElementById('btn-help').addEventListener('click', () => {{
        shortcutsModal.classList.add('active');
      }});
      document.getElementById('shortcuts-close').addEventListener('click', () => {{
        shortcutsModal.classList.remove('active');
      }});
      shortcutsModal.addEventListener('click', (e) => {{
        if (e.target === shortcutsModal) shortcutsModal.classList.remove('active');
      }});

      // ==================== 7. 全局键盘快捷键 ====================
      window.addEventListener('keydown', (e) => {{
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {{
          if (e.key === 'Escape') {{
            searchInput.value = '';
            activeQuery = '';
            matchedMarks = [];
            currentMatchIdx = -1;
            searchCount.textContent = '';
            searchPrev.style.display = 'none';
            searchNext.style.display = 'none';
            e.target.blur();
            clearSearchHighlight();
          }}
          return;
        }}

        if (e.key === '/' || ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f')) {{
          e.preventDefault();
          searchInput.focus();
        }} else if (e.key === '+' || e.key === '=') {{
          e.preventDefault();
          if (lightbox.classList.contains('active')) {{
            document.getElementById('lightbox-zoom-in').click();
          }} else {{
            mm.rescale(1.25);
          }}
        }} else if (e.key === '-' || e.key === '_') {{
          e.preventDefault();
          if (lightbox.classList.contains('active')) {{
            document.getElementById('lightbox-zoom-out').click();
          }} else {{
            mm.rescale(0.8);
          }}
        }} else if (e.key === '1') {{
          document.getElementById('btn-fold-1').click();
        }} else if (e.key === '2') {{
          document.getElementById('btn-fold-2').click();
        }} else if (e.key === '3') {{
          document.getElementById('btn-fold-3').click();
        }} else if (e.key === '0') {{
          document.getElementById('btn-expand').click();
        }} else if (e.key === ' ') {{
          e.preventDefault();
          mm.fit();
        }} else if (e.key === 't' || e.key === 'T') {{
          toggleTheme();
        }} else if (e.key === 'f' || e.key === 'F') {{
          toggleFullscreen();
        }} else if (e.key === '?' || e.key === '¿') {{
          shortcutsModal.classList.toggle('active');
        }} else if (e.key === 'Escape') {{
          lightbox.classList.remove('active');
          shortcutsModal.classList.remove('active');
          exportDropdown.classList.remove('active');
          searchInput.value = '';
          activeQuery = '';
          matchedMarks = [];
          currentMatchIdx = -1;
          searchCount.textContent = '';
          searchPrev.style.display = 'none';
          searchNext.style.display = 'none';
          clearSearchHighlight();
        }}
      }});
    }});
  </script>
</body>
</html>
"""

def embed_images_as_base64(markdown_text, base_dir):
    """
    将 Markdown 中的本地相对路径图片转为 Base64 编码内嵌，
    实现 100% 独立离线单文件分发。
    """
    def replace_img(match):
        alt = match.group(1)
        src = match.group(2).strip()
        # 跳过网络链接或已内嵌的 data:url
        if src.startswith(('http://', 'https://', 'data:')):
            return match.group(0)
        
        img_path = (Path(base_dir) / src).resolve()
        if img_path.exists() and img_path.is_file():
            mime_type, _ = mimetypes.guess_type(str(img_path))
            if not mime_type:
                mime_type = 'image/png'
            try:
                with open(img_path, 'rb') as f:
                    encoded = base64.b64encode(f.read()).decode('utf-8')
                return f'![{alt}](data:{mime_type};base64,{encoded})'
            except Exception as e:
                print(f"[!] 图片内嵌失败 {src}: {e}", file=sys.stderr)
        return match.group(0)

    img_pattern = re.compile(r'!\[(.*?)\]\((.*?)\)')
    return img_pattern.sub(replace_img, markdown_text)

def extract_mindmap_markdown(md_text):
    """
    提取 Markdown 中适合用于思维导图的核心树形结构。
    跳过 mermaid 代码块与普通引言，保留标题、微表格与多模态图片。
    """
    lines = md_text.splitlines()
    tree_lines = []
    in_code_block = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        
        # 保留标题、列表项、引用、图片与表格
        if stripped.startswith(("#", "-", "*", "+", "!", "|", ">", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
            tree_lines.append(line)
        elif not stripped:
            tree_lines.append("")
        elif line.startswith("  ") or line.startswith("\t"):
            # 缩进续行
            tree_lines.append(line)
    
    clean_md = "\n".join(tree_lines).strip()
    return clean_md if clean_md else md_text

def convert_md_to_html(md_path, html_path=None, title=None, embed_images=False):
    if not os.path.exists(md_path):
        raise FileNotFoundError(f"未找到 Markdown 文件: {md_path}")
    
    with open(md_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    # 提取标题
    if not title:
        first_title = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = first_title.group(1).strip() if first_title else Path(md_path).stem

    # 过滤与抽取导图树
    mindmap_md = extract_mindmap_markdown(content)
    
    # 离线便携模式：内嵌 Base64 图片
    if embed_images:
        base_dir = Path(md_path).parent
        mindmap_md = embed_images_as_base64(mindmap_md, base_dir)
        print(f"[+] 已完成本地图片 Base64 编码内嵌，产物为完全便携单文件")
    
    if not html_path:
        html_path = str(Path(md_path).with_suffix(".html"))

    # 处理基础引擎 JS 脚本（若开启 embed_images 且本地存在离线库，则直接内嵌，实现 100% 独立离线单文件）
    vendor_dir = Path(__file__).resolve().parent.parent / "assets" / "vendor"
    vendor_files = ["d3.min.js", "markmap-view.min.js", "markmap-lib.min.js", "jszip.min.js"]
    can_inline = embed_images and vendor_dir.exists() and all((vendor_dir / vf).exists() for vf in vendor_files)

    if can_inline:
        inlined = []
        for vf in vendor_files:
            with open(vendor_dir / vf, "r", encoding="utf-8", errors="replace") as f_js:
                inlined.append(f"  <script>\n{f_js.read()}\n  </script>")
        vendor_scripts_tag = "\n".join(inlined)
        print(f"[+] 已完成前端核心引擎 (d3, markmap, jszip) 本地内嵌，实现真正 100% 离线自包含")
    else:
        vendor_scripts_tag = (
            '  <script src="https://cdn.jsdelivr.net/npm/d3@7"></script>\n'
            '  <script src="https://cdn.jsdelivr.net/npm/markmap-view@0.17.0"></script>\n'
            '  <script src="https://cdn.jsdelivr.net/npm/markmap-lib@0.17.0"></script>\n'
            '  <script src="https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js"></script>'
        )

    rendered_html = HTML_TEMPLATE.format(
        title=title,
        title_json=json.dumps(title, ensure_ascii=False),
        markdown_json=json.dumps(mindmap_md, ensure_ascii=False)
    )
    rendered_html = rendered_html.replace("<!-- VENDOR_SCRIPTS_PLACEHOLDER -->", vendor_scripts_tag)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(rendered_html)

    print(f"[+] 工业级交互式思维导图 HTML 已生成: {html_path}")
    return html_path

def main():
    parser = argparse.ArgumentParser(description="Markdown 导图转工业级单文件交互式 HTML 工具")
    parser.add_argument("md_file", help="输入 Markdown 文件路径")
    parser.add_argument("-o", "--output", help="输出 HTML 文件路径（可选，默认为同名 .html）")
    parser.add_argument("-t", "--title", help="导图标题（可选）")
    parser.add_argument("--embed-images", action="store_true", help="将本地相对路径图片内嵌为 Base64（完全离线便携）")
    args = parser.parse_args()

    convert_md_to_html(args.md_file, args.output, args.title, embed_images=args.embed_images)

if __name__ == "__main__":
    main()
