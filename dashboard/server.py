"""
dashboard/server.py - Friday Local Web Dashboard & Admin Interface Server
Serves a sleek futuristic web dashboard on http://localhost:8000 displaying
system metrics, indexed skills/tools, app index, credentials config, and WebRTC voice call.
"""
import os
import sys
import asyncio
import threading
import psutil
import webbrowser
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body
from fastapi.responses import HTMLResponse, JSONResponse
from config.settings import (
    WEBRTC_PORT, get_github_token, get_groq_key, get_telegram_token, get_authorized_user_ids,
    save_env_values
)
from memory.memory_manager import read_soul_profile, STAGE_LABELS
from tools.apps import load_known_apps
from core.agent_loop import process_user_input, process_user_input_with_metadata
from core.logger import logger

app = FastAPI(title="Friday AI Local Web Dashboard")
server_thread = None

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FRIDAY AI — System Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@300;400;500;700&family=Outfit:wght@400;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/dompurify@3.0.6/dist/purify.min.js"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        :root {
            --bg-color: #030407;
            --primary-glow: rgba(255, 255, 255, 0.85);
            --text-main: #ffffff;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body, html {
            width: 100%;
            height: 100%;
            overflow: hidden;
            background-color: var(--bg-color);
            font-family: 'Orbitron', sans-serif;
            color: var(--text-main);
        }

        /* Fullscreen Cinematic Intro Overlay */
        #intro-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: #030407;
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 9999;
            animation: fadeOverlay 0.6s ease-out 3.8s forwards;
            pointer-events: none;
        }

        /* Container holding letters during spawn and compression */
        .title-wrapper {
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            animation: compressToPoint 0.6s cubic-bezier(0.7, 0, 0.3, 1) 2.5s forwards;
        }

        .title-text {
            font-family: 'Orbitron', sans-serif;
            font-size: 76px;
            font-weight: 400;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            display: flex;
            padding-left: 0.12em;
            gap: 2px;
            color: #ffffff;
            text-shadow: 0 0 25px rgba(255, 255, 255, 0.9), 0 0 50px rgba(255, 255, 255, 0.5);
        }

        /* NEW ANIMATION TYPE: 3D Quantum Depth Focal Convergence */
        .letter {
            opacity: 0;
            transform: perspective(800px) translateZ(220px) scale(2.2);
            filter: blur(25px) brightness(3);
            display: inline-block;
            animation: letterSpawn3D 0.85s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        .letter:nth-child(1) { animation-delay: 0.18s; }
        .letter:nth-child(2) { animation-delay: 0.42s; }
        .letter:nth-child(3) { animation-delay: 0.66s; }
        .letter:nth-child(4) { animation-delay: 0.90s; }
        .letter:nth-child(5) { animation-delay: 1.14s; }
        .letter:nth-child(6) { animation-delay: 1.38s; }

        @keyframes letterSpawn3D {
            0% {
                opacity: 0;
                transform: perspective(800px) translateZ(220px) scale(2.2);
                filter: blur(25px) brightness(3);
            }
            60% {
                opacity: 0.85;
                filter: blur(4px) brightness(1.8);
            }
            100% {
                opacity: 1;
                transform: perspective(800px) translateZ(0) scale(1);
                filter: blur(0) brightness(1);
            }
        }

        /* Compression to line keyframe */
        @keyframes compressToPoint {
            0% {
                transform: scale(1);
                opacity: 1;
                filter: blur(0);
            }
            70% {
                transform: scaleX(0.15) scaleY(0.02);
                opacity: 1;
                filter: blur(2px);
            }
            100% {
                transform: scaleX(0.02) scaleY(0.02);
                opacity: 0;
                filter: blur(5px);
            }
        }

        /* Horizontal Split Lines */
        .line-split-container {
            position: absolute;
            width: 100vw;
            height: 4px;
            display: flex;
            justify-content: center;
            align-items: center;
            pointer-events: none;
        }

        .line-half {
            position: absolute;
            height: 3px;
            width: 50vw;
            box-shadow: 0 0 15px rgba(255, 255, 255, 0.9), 0 0 30px rgba(255, 255, 255, 0.5);
            opacity: 0;
        }

        .line-left {
            right: 50%;
            transform-origin: right center;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.85) 80%, #ffffff);
            animation: shootLeft 0.55s cubic-bezier(0.16, 1, 0.3, 1) 3.0s forwards;
        }

        .line-right {
            left: 50%;
            transform-origin: left center;
            background: linear-gradient(270deg, transparent, rgba(255, 255, 255, 0.85) 80%, #ffffff);
            animation: shootRight 0.55s cubic-bezier(0.16, 1, 0.3, 1) 3.0s forwards;
        }

        @keyframes shootLeft {
            0% {
                opacity: 1;
                transform: scaleX(0.05) translateX(0);
            }
            40% {
                opacity: 1;
                transform: scaleX(1) translateX(-20vw);
            }
            100% {
                opacity: 0;
                transform: scaleX(0.8) translateX(-100vw);
            }
        }

        @keyframes shootRight {
            0% {
                opacity: 1;
                transform: scaleX(0.05) translateX(0);
            }
            40% {
                opacity: 1;
                transform: scaleX(1) translateX(20vw);
            }
            100% {
                opacity: 0;
                transform: scaleX(0.8) translateX(100vw);
            }
        }

        @keyframes fadeOverlay {
            0% {
                opacity: 1;
                visibility: visible;
            }
            100% {
                opacity: 0;
                visibility: hidden;
            }
        }

        /* Main Dashboard Stage */
        #main-dashboard {
            width: 100vw;
            height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            gap: 24px;
            padding: 24px;
            background: radial-gradient(circle at center, rgba(255, 255, 255, 0.04) 0%, rgba(3, 4, 7, 1) 75%);
            opacity: 0;
            animation: showDashboard 0.8s ease-out 0.5s forwards;
            box-sizing: border-box;
            transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .control-block {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 24px;
            transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1);
            order: 2;
        }

        #response-pill {
            order: 1;
        }

        /* Expanded Mode (Horizontal Layout for >3 lines) */
        #main-dashboard.expanded {
            flex-direction: row;
            align-items: center;
            justify-content: center;
            gap: 45px;
            padding: 40px;
        }

        #main-dashboard.expanded .control-block {
            order: 1;
            flex-shrink: 0;
        }

        #main-dashboard.expanded #response-pill {
            order: 2;
            max-width: 660px;
            max-height: calc(85vh - 60px);
            text-align: left;
        }

        .friday-frame {
            position: relative;
            display: inline-flex;
            padding: 1.5px;
            background: rgba(255, 255, 255, 0.2);
            box-shadow: 0 16px 45px rgba(0, 0, 0, 0.7), inset 0 1px 1px rgba(255, 255, 255, 0.35), inset 0 -3px 8px rgba(0, 0, 0, 0.7);
            clip-path: polygon(
                22px 0%, 
                100% 0%, 
                100% calc(100% - 22px), 
                calc(100% - 22px) 100%, 
                0% 100%, 
                0% 22px
            );
        }

        .friday-frame-inner {
            background: rgba(32, 32, 32, 0.88);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            padding: 22px 56px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.25), inset 0 -2px 6px rgba(0, 0, 0, 0.6);
            clip-path: polygon(
                21px 0%, 
                100% 0%, 
                100% calc(100% - 21px), 
                calc(100% - 21px) 100%, 
                0% 100%, 
                0% 21px
            );
        }

        .centered-friday {
            font-family: 'Orbitron', sans-serif;
            font-size: 46px;
            font-weight: 600;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: #f8fafc;
            text-shadow: 0 1px 1px rgba(255, 255, 255, 0.4), 0 -1px 2px rgba(0, 0, 0, 0.9), 0 4px 15px rgba(0, 0, 0, 0.7);
            padding-left: 0.14em;
            transition: all 0.4s ease;
            text-align: center;
            word-break: break-word;
            line-height: 1.45;
        }

        .centered-friday.pulsing {
            color: #ffffff;
            animation: fridayPulseGlow 1.6s ease-in-out infinite alternate;
        }

        @keyframes fridayPulseGlow {
            0% {
                text-shadow: 0 0 8px rgba(255, 255, 255, 0.4), 0 0 16px rgba(255, 255, 255, 0.2);
                transform: scale(1);
            }
            100% {
                text-shadow: 0 0 18px rgba(255, 255, 255, 0.75), 0 0 32px rgba(255, 255, 255, 0.45);
                transform: scale(1.02);
            }
        }

        /* AI Output Bar (Response Pill) Above Center Box */
        .response-pill {
            position: relative;
            width: min(560px, calc(100vw - 48px));
            max-width: 560px;
            background: rgba(32, 32, 32, 0.88);
            border: 1px solid rgba(255, 255, 255, 0.16);
            border-radius: 24px;
            padding: 16px 26px;
            color: #ffffff;
            font-family: 'Outfit', sans-serif;
            font-size: 15.5px;
            line-height: 1.6;
            text-align: left;
            word-break: break-word;
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 1px rgba(255, 255, 255, 0.2);
            box-sizing: border-box;
            transition: width 0.4s ease, max-width 0.4s ease, opacity 0.3s ease;
            opacity: 1;
            overflow: visible;
        }

        #main-dashboard.expanded .response-pill {
            width: min(740px, calc(100vw - 48px));
            max-width: 740px;
        }

        /* Floating Action Pill Bar for Copy & Regenerate (Outside Output Box) */
        .response-action-bar {
            position: absolute;
            bottom: calc(100% + 6px);
            right: 12px;
            display: flex;
            align-items: center;
            gap: 4px;
            z-index: 30;
            background: rgba(32, 32, 32, 0.88);
            border: 1px solid rgba(255, 255, 255, 0.16);
            border-radius: 20px;
            padding: 4px 8px;
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 1px rgba(255, 255, 255, 0.2);
            opacity: 0;
            pointer-events: none;
            transform: translateY(6px) scale(0.96);
            transition: opacity 0.25s cubic-bezier(0.16, 1, 0.3, 1) 0.2s, transform 0.25s cubic-bezier(0.16, 1, 0.3, 1) 0.2s;
        }

        /* Transparent hover bridge covering the gap between response box and action bar */
        .response-action-bar::before {
            content: '';
            position: absolute;
            top: 100%;
            left: -12px;
            right: -12px;
            height: 18px;
            background: transparent;
        }

        .response-pill:hover .response-action-bar,
        .response-action-bar:hover {
            opacity: 1;
            pointer-events: auto;
            transform: translateY(0) scale(1);
            transition-delay: 0s;
        }

        .pill-action-btn {
            background: transparent;
            border: none;
            border-radius: 14px;
            color: #cbd5e1;
            padding: 4px 10px;
            font-family: 'Outfit', sans-serif;
            font-size: 12px;
            font-weight: 500;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
            user-select: none;
        }

        .pill-action-btn i, .pill-action-btn svg {
            width: 14px;
            height: 14px;
            stroke-width: 2;
            flex-shrink: 0;
        }

        .pill-action-btn:hover {
            background: rgba(255, 255, 255, 0.15);
            color: #ffffff;
            transform: translateY(-1px);
        }

        .pill-action-btn:active {
            transform: scale(0.94);
        }

        .pill-action-btn:disabled {
            opacity: 0.4;
            cursor: not-allowed;
            transform: none;
        }

        /* Markdown Formatting Typography & Layout */
        #response-text {
            display: block;
            width: 100%;
            max-height: 260px;
            overflow-y: auto;
            font-family: 'Outfit', sans-serif;
            font-size: 15.5px;
            line-height: 1.6;
            color: #f8fafc;
            padding-right: 4px;
        }

        #main-dashboard.expanded #response-text {
            max-height: calc(88vh - 50px);
        }

        #response-text::-webkit-scrollbar {
            width: 5px;
        }

        #response-text::-webkit-scrollbar-track {
            background: transparent;
        }

        #response-text::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.2);
            border-radius: 4px;
        }

        #response-text::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.4);
        }

        #response-text p {
            margin-bottom: 10px;
        }
        #response-text p:last-child {
            margin-bottom: 0;
        }

        #response-text h1, #response-text h2, #response-text h3, #response-text h4, #response-text h5, #response-text h6 {
            font-family: 'Outfit', sans-serif;
            color: #ffffff;
            margin-top: 14px;
            margin-bottom: 6px;
            line-height: 1.3;
        }
        #response-text h1 { font-size: 1.35em; font-weight: 700; border-bottom: 1px solid rgba(255, 255, 255, 0.12); padding-bottom: 4px; }
        #response-text h2 { font-size: 1.2em; font-weight: 700; }
        #response-text h3 { font-size: 1.1em; font-weight: 600; }
        #response-text h4 { font-size: 1.0em; font-weight: 600; }

        #response-text ul, #response-text ol {
            margin: 8px 0 10px 22px;
            padding: 0;
        }
        #response-text li {
            margin-bottom: 4px;
        }
        #response-text li > ul, #response-text li > ol {
            margin-top: 4px;
            margin-bottom: 4px;
        }

        #response-text blockquote {
            border-left: 3px solid rgba(255, 255, 255, 0.4);
            padding: 4px 12px;
            margin: 10px 0;
            color: #cbd5e1;
            font-style: italic;
            background: rgba(255, 255, 255, 0.04);
            border-radius: 0 6px 6px 0;
        }

        #response-text hr {
            border: none;
            border-top: 1px solid rgba(255, 255, 255, 0.15);
            margin: 14px 0;
        }

        #response-text a {
            color: #38bdf8;
            text-decoration: underline;
            text-underline-offset: 3px;
            transition: color 0.15s ease;
        }
        #response-text a:hover {
            color: #7dd3fc;
        }

        /* Inline Code Styling */
        #response-text code:not(pre code) {
            background: rgba(255, 255, 255, 0.12);
            color: #f1f5f9;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'JetBrains Mono', Consolas, monospace;
            font-size: 0.88em;
            word-break: break-word;
        }

        /* ChatGPT-Style Modern Code Block Containers */
        #response-text pre {
            background: rgba(12, 16, 26, 0.95);
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-radius: 10px;
            margin: 12px 0;
            padding: 12px 16px;
            overflow-x: auto;
            max-width: 100%;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
            box-sizing: border-box;
        }

        #response-text pre code {
            font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
            font-size: 13px;
            line-height: 1.5;
            color: #e2e8f0;
            background: transparent;
            padding: 0;
            border-radius: 0;
            display: block;
            white-space: pre;
        }

        /* Language Banner Header for Code Blocks */
        .code-block-wrapper {
            background: rgba(12, 16, 26, 0.95);
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-radius: 10px;
            margin: 12px 0;
            overflow: hidden;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
        }
        .code-block-header {
            background: rgba(255, 255, 255, 0.06);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            padding: 4px 12px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            color: #94a3b8;
            text-transform: lowercase;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .code-block-wrapper pre {
            border: none;
            border-radius: 0;
            margin: 0;
            box-shadow: none;
        }

        /* Tables */
        #response-text table {
            width: 100%;
            border-collapse: collapse;
            margin: 12px 0;
            font-size: 13.5px;
        }
        #response-text th, #response-text td {
            border: 1px solid rgba(255, 255, 255, 0.15);
            padding: 8px 12px;
            text-align: left;
        }
        #response-text th {
            background: rgba(255, 255, 255, 0.08);
            font-weight: 600;
            color: #ffffff;
        }
        #response-text tr:nth-child(even) {
            background: rgba(255, 255, 255, 0.02);
        }



        .response-pill.hidden {
            display: none;
            opacity: 0;
        }

        .response-pill.thinking {
            font-style: italic;
            color: rgba(255, 255, 255, 0.7);
        }

        /* Subtle Glassmorphism Sources Section */
        .response-sources {
            margin-top: 12px;
            padding-top: 10px;
            border-top: 1px solid rgba(255, 255, 255, 0.12);
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 8px;
            font-family: 'Outfit', sans-serif;
            font-size: 12px;
        }

        .response-sources.hidden {
            display: none;
        }

        .sources-title {
            color: rgba(255, 255, 255, 0.45);
            font-weight: 600;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-right: 2px;
        }

        .source-chip {
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 16px;
            color: rgba(255, 255, 255, 0.85);
            padding: 3px 10px;
            text-decoration: none;
            font-size: 12px;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            max-width: 220px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .source-chip:hover {
            background: rgba(255, 255, 255, 0.16);
            border-color: rgba(255, 255, 255, 0.35);
            color: #ffffff;
            transform: translateY(-1px);
        }

        /* Center Input Box Below Box */
        .input-container {
            width: 90%;
            max-width: 440px;
            display: flex;
            align-items: center;
            gap: 12px;
            background: rgba(32, 32, 32, 0.88);
            border: 1px solid rgba(255, 255, 255, 0.16);
            border-radius: 40px;
            padding: 8px 12px 8px 20px;
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            transition: border-color 0.3s ease;
            box-sizing: border-box;
        }

        .input-container:focus-within {
            border-color: rgba(255, 255, 255, 0.3);
            box-shadow: none;
        }

        .input-container input {
            flex: 1;
            background: transparent;
            border: none;
            outline: none;
            color: #ffffff;
            font-family: 'Outfit', sans-serif;
            font-size: 15px;
            padding: 8px 0;
        }

        .input-container input::placeholder {
            color: rgba(255, 255, 255, 0.35);
        }

        .input-send-btn {
            background: transparent;
            border: none;
            color: rgba(255, 255, 255, 0.7);
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.2s ease;
            flex-shrink: 0;
        }

        .input-send-btn:hover {
            background: transparent;
            color: #ffffff;
            transform: scale(1.1);
        }

        .input-send-btn:active {
            transform: scale(0.95);
        }

        @keyframes showDashboard {
            from {
                opacity: 0;
                transform: scale(0.96);
            }
            to {
                opacity: 1;
                transform: scale(1);
            }
        }

        /* Floating Pill Dock */
        .pill-dock-container {
            position: fixed;
            top: 24px;
            right: 24px;
            z-index: 1000;
            display: flex;
            align-items: center;
        }

        .pill-dock {
            position: relative;
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 6px 14px;
            background: rgba(32, 32, 32, 0.88);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 40px;
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            box-shadow: 0 14px 35px rgba(0, 0, 0, 0.65), inset 0 1px 1px rgba(255, 255, 255, 0.3), inset 0 -2px 6px rgba(0, 0, 0, 0.6);
        }

        .dock-btn {
            background: transparent;
            border: none;
            color: #ffffff;
            width: 38px;
            height: 38px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .dock-btn:hover {
            background: rgba(255, 255, 255, 0.12);
            color: #ffffff;
            transform: scale(1.05);
        }

        .dock-btn:active {
            transform: scale(0.95);
        }

        /* Power Dropdown Popup */
        .power-dropdown {
            position: absolute;
            top: calc(100% + 12px);
            right: 0;
            left: auto;
            min-width: 190px;
            background: rgba(32, 32, 32, 0.96);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 12px;
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            box-shadow: 0 16px 40px rgba(0, 0, 0, 0.7), inset 0 1px 1px rgba(255, 255, 255, 0.25), inset 0 -1px 4px rgba(0, 0, 0, 0.5);
            display: flex;
            flex-direction: column;
            padding: 6px;
            gap: 4px;
            opacity: 0;
            visibility: hidden;
            transform: translateY(-8px) scale(0.95);
            transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
            z-index: 1001;
        }

        .power-dropdown::before {
            content: '';
            position: absolute;
            top: -6px;
            right: 62px;
            left: auto;
            width: 10px;
            height: 10px;
            background: rgba(32, 32, 32, 0.96);
            border-left: 1px solid rgba(255, 255, 255, 0.2);
            border-top: 1px solid rgba(255, 255, 255, 0.2);
            transform: rotate(45deg);
        }

        .power-dropdown.active {
            opacity: 1;
            visibility: visible;
            transform: translateY(0) scale(1);
        }

        .dropdown-item {
            background: transparent;
            border: none;
            color: #cbd5e1;
            padding: 10px 14px;
            font-family: 'Outfit', sans-serif;
            font-size: 13px;
            font-weight: 500;
            border-radius: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
            cursor: pointer;
            transition: all 0.15s ease;
            text-align: left;
        }

        .dropdown-item:hover {
            background: rgba(255, 255, 255, 0.12);
            color: #ffffff;
        }

        .dropdown-item.danger:hover {
            background: rgba(255, 23, 68, 0.2);
            color: #ff5252;
        }


        #chat-send-btn:active { transform: scale(0.9); }

        /* Settings Modal Backdrop & Window */
        .modal-backdrop {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: rgba(3, 4, 7, 0.7);
            backdrop-filter: blur(6px);
            -webkit-backdrop-filter: blur(6px);
            z-index: 2000;
            display: flex;
            justify-content: center;
            align-items: center;
            opacity: 0;
            visibility: hidden;
            transition: all 0.25s ease;
        }

        .modal-backdrop.active {
            opacity: 1;
            visibility: visible;
        }

        .settings-window {
            width: 380px;
            height: 240px;
            background: rgba(10, 14, 26, 0.95);
            border: 1px solid rgba(0, 242, 254, 0.3);
            border-radius: 16px;
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.7), 0 0 30px rgba(0, 242, 254, 0.15);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            transform: scale(0.9);
            transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .modal-backdrop.active .settings-window {
            transform: scale(1);
        }

        .settings-header {
            height: 48px;
            padding: 0 16px;
            background: rgba(0, 242, 254, 0.05);
            border-bottom: 1px solid rgba(0, 242, 254, 0.15);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .settings-title {
            font-family: 'Orbitron', sans-serif;
            font-size: 14px;
            font-weight: 600;
            letter-spacing: 0.08em;
            color: #00f2fe;
        }

        .close-btn {
            background: transparent;
            border: none;
            color: #94a3b8;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            font-size: 16px;
            transition: all 0.2s ease;
        }

        .close-btn:hover {
            background: rgba(255, 23, 68, 0.2);
            color: #ff5252;
        }

        .settings-body {
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'Outfit', sans-serif;
            font-size: 32px;
            font-weight: 700;
            color: #ffffff;
            letter-spacing: 1px;
        }
    </style>
</head>
<body>

    <!-- Floating Pill Dock -->
    <div class="pill-dock-container">
        <div class="pill-dock">
            <button class="dock-btn" id="btn-power" title="Power Options">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M11 2h2v10h-2z"></path>
                    <path d="M15 4.53v2.16c2.36 1.13 4 3.53 4 6.32 0 3.86-3.14 7-7 7s-7-3.14-7-7c0-2.79 1.64-5.19 4-6.32V4.53C5.51 5.77 3 9.1 3 13c0 4.96 4.04 9 9 9s9-4.04 9-9c0-3.91-2.51-7.24-6-8.47"></path>
                </svg>
            </button>
            <button class="dock-btn" id="btn-settings" title="Settings">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 8c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4m0 6c-1.08 0-2-.92-2-2s.92-2 2-2 2 .92 2 2-.92 2-2 2"></path>
                    <path d="m20.42 13.4-.51-.29c.05-.37.08-.74.08-1.11s-.03-.74-.08-1.11l.51-.29c.96-.55 1.28-1.78.73-2.73l-1-1.73a2.006 2.006 0 0 0-2.73-.73l-.53.31c-.58-.46-1.22-.83-1.9-1.11v-.6c0-1.1-.9-2-2-2h-2c-1.1 0-2 .9-2 2v.6c-.67.28-1.31.66-1.9 1.11l-.53-.31c-.96-.55-2.18-.22-2.73.73l-1 1.73c-.55.96-.22 2.18.73 2.73l.51.29c-.05.37-.08.74-.08 1.11s.03.74.08 1.11l-.51.29c-.96.55-1.28 1.78-.73 2.73l1 1.73c.55.95 1.77 1.28 2.73.73l.53-.31c.58.46 1.22.83 1.9 1.11v.6c0 1.1.9 2 2 2h2c1.1 0 2-.9 2-2v-.6a8.7 8.7 0 0 0 1.9-1.11l.53.31c.95.55 2.18.22 2.73-.73l1-1.73c.55-.96.22-2.18-.73-2.73m-2.59-2.78c.11.45.17.92.17 1.38s-.06.92-.17 1.38a1 1 0 0 0 .47 1.11l1.12.65-1 1.73-1.14-.66c-.38-.22-.87-.16-1.19.14-.68.65-1.51 1.13-2.38 1.4-.42.13-.71.52-.71.96v1.3h-2v-1.3c0-.44-.29-.83-.71-.96-.88-.27-1.7-.75-2.38-1.4a1.01 1.01 0 0 0-1.19-.15l-1.14.66-1-1.73 1.12-.65c.39-.22.58-.68.47-1.11-.11-.45-.17-.92-.17-1.38s.06-.93.17-1.38A1 1 0 0 0 5.7 9.5l-1.12-.65 1-1.73 1.14.66c.38.22.87.16 1.19-.14.68-.65 1.51-1.13 2.38-1.4.42-.13.71-.52.71-.96v-1.3h2v1.3c0 .44.29.83.71.96.88.27 1.7.75 2.38 1.4.32.31.81.36 1.19.14l1.14-.66 1 1.73-1.12.65c-.39.22-.58.68-.47 1.11Z"></path>
                </svg>
            </button>

            <!-- Dropdown Popup Emerging from Power Button -->
            <div class="power-dropdown" id="power-dropdown">
                <button class="dropdown-item danger" id="btn-shutdown">
                    <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24"><path d="M11 2h2v10h-2z"></path><path d="M15 4.53v2.16c2.36 1.13 4 3.53 4 6.32 0 3.86-3.14 7-7 7s-7-3.14-7-7c0-2.79 1.64-5.19 4-6.32V4.53C5.51 5.77 3 9.1 3 13c0 4.96 4.04 9 9 9s9-4.04 9-9c0-3.91-2.51-7.24-6-8.47"></path></svg>
                    Shutdown (Friday)
                </button>
                <button class="dropdown-item" id="btn-restart">
                    <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24"><path d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46A7.93 7.93 0 0 0 20 12c0-4.42-3.58-8-8-8zm-6 8c0-1.01.25-1.97.7-2.8L5.24 7.74A7.93 7.93 0 0 0 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3c-3.31 0-6-2.69-6-6z"></path></svg>
                    Restart (Friday)
                </button>
                <button class="dropdown-item" id="btn-update">
                    <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14v-4H8l4-4 4 4h-3v4h-2z"></path></svg>
                    Update (Friday)
                </button>
            </div>
        </div>
    </div>

    <!-- Settings Modal Window -->
    <div class="modal-backdrop" id="settings-backdrop">
        <div class="settings-window">
            <div class="settings-header">
                <span class="settings-title">SETTINGS</span>
                <button class="close-btn" id="btn-close-settings" title="Close Window">✕</button>
            </div>
            <div class="settings-body">
                Hi
            </div>
        </div>
    </div>

    <!-- Cinematic Intro Overlay -->
    <div id="intro-overlay">
        <div class="title-wrapper">
            <div class="title-text">
                <span class="letter">F</span>
                <span class="letter">R</span>
                <span class="letter">I</span>
                <span class="letter">D</span>
                <span class="letter">A</span>
                <span class="letter">Y</span>
            </div>
        </div>

        <div class="line-split-container">
            <div class="line-half line-left"></div>
            <div class="line-half line-right"></div>
        </div>
    </div>

    <!-- Main Dashboard Stage -->
    <main id="main-dashboard">
        <!-- Control Block (FRIDAY Box + Input Bar) -->
        <div class="control-block" id="control-block">
            <!-- Center FRIDAY Box -->
            <div class="friday-frame" id="friday-frame">
                <div class="friday-frame-inner" id="friday-frame-inner">
                    <h1 class="centered-friday" id="centered-friday-text">FRIDAY</h1>
                </div>
            </div>

            <!-- Input Box Below Center Box -->
            <div class="input-container">
                <input type="text" id="chat-input" placeholder="Ask Friday or type a command..." autocomplete="off">
                <button class="input-send-btn" id="chat-send-btn" title="Send Input">
                    <svg width="18" height="18" fill="currentColor" viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path></svg>
                </button>
            </div>
        </div>

        <!-- AI Output Response Pill -->
        <div id="response-pill" class="response-pill hidden">
            <div class="response-action-bar" id="response-action-bar">
                <button class="pill-action-btn" id="btn-copy-response" title="Copy original Markdown">
                    <i data-lucide="copy" id="copy-icon"></i>
                    <span id="copy-btn-label">Copy</span>
                </button>
                <button class="pill-action-btn" id="btn-regenerate-response" title="Regenerate AI response">
                    <i data-lucide="rotate-cw" id="regen-icon"></i>
                    <span>Regenerate</span>
                </button>
            </div>
            <div id="response-text"></div>
            <div id="response-sources" class="response-sources hidden"></div>
        </div>
    </main>

    <script>
        setTimeout(() => {
            const overlay = document.getElementById('intro-overlay');
            if (overlay) {
                overlay.style.display = 'none';
            }
        }, 4600);

        // Pill Dock Interactivity
        const btnPower = document.getElementById('btn-power');
        const powerDropdown = document.getElementById('power-dropdown');
        const btnSettings = document.getElementById('btn-settings');
        const settingsBackdrop = document.getElementById('settings-backdrop');
        const btnCloseSettings = document.getElementById('btn-close-settings');

        const btnShutdown = document.getElementById('btn-shutdown');
        const btnRestart = document.getElementById('btn-restart');
        const btnUpdate = document.getElementById('btn-update');

        // Input, Pulse Glow & Static Response Pill Controller
        const mainDashboard = document.getElementById('main-dashboard');
        const chatInput = document.getElementById('chat-input');
        const chatSendBtn = document.getElementById('chat-send-btn');
        const responsePill = document.getElementById('response-pill');
        const responseText = document.getElementById('response-text');
        const fridayText = document.getElementById('centered-friday-text');

        const btnCopy = document.getElementById('btn-copy-response');
        const btnRegen = document.getElementById('btn-regenerate-response');

        let hideTimer = null;
        let lastUserPrompt = '';
        let lastResponseText = '';

        function refreshLucideIcons() {
            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                try {
                    window.lucide.createIcons();
                } catch(e) {}
            }
        }

        document.addEventListener('DOMContentLoaded', () => {
            refreshLucideIcons();
        });
        setTimeout(refreshLucideIcons, 500);

        async function copyResponseToClipboard() {
            if (!lastResponseText) return;
            const copyLabel = document.getElementById('copy-btn-label');
            const copyIcon = document.getElementById('copy-icon');
            try {
                await navigator.clipboard.writeText(lastResponseText);
                if (copyLabel) copyLabel.textContent = 'Copied!';
                if (copyIcon) copyIcon.setAttribute('data-lucide', 'check');
                refreshLucideIcons();
                setTimeout(() => {
                    if (copyLabel) copyLabel.textContent = 'Copy';
                    if (copyIcon) copyIcon.setAttribute('data-lucide', 'copy');
                    refreshLucideIcons();
                }, 1500);
            } catch (err) {
                console.error('Clipboard copy failed:', err);
                if (copyLabel) copyLabel.textContent = 'Failed';
                setTimeout(() => {
                    if (copyLabel) copyLabel.textContent = 'Copy';
                }, 1500);
            }
        }

        async function regenerateResponse() {
            if (!lastUserPrompt) return;
            if (chatInput && chatInput.disabled) return;

            if (chatInput) chatInput.disabled = true;
            if (chatSendBtn) chatSendBtn.disabled = true;
            if (btnRegen) btnRegen.disabled = true;

            if (fridayText) {
                fridayText.classList.add('pulsing');
            }

            responsePill.classList.remove('hidden');
            responseText.textContent = 'Regenerating...';

            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: lastUserPrompt })
                });

                if (!res.ok) {
                    throw new Error(`HTTP ${res.status}`);
                }

                const data = await res.json();
                lastResponseText = data.response || 'No response.';
                showResponsePill(lastResponseText, data.sources || [], data.used_web || false);
            } catch (error) {
                console.error('Regeneration failed:', error);
                showResponsePill('Error: ' + error.message);
            } finally {
                if (fridayText) {
                    fridayText.classList.remove('pulsing');
                }
                if (btnRegen) btnRegen.disabled = false;
                if (chatInput) chatInput.disabled = false;
                if (chatSendBtn) chatSendBtn.disabled = false;
                if (chatInput) chatInput.focus();
            }
        }

        if (btnCopy) {
            btnCopy.addEventListener('click', (e) => {
                e.stopPropagation();
                copyResponseToClipboard();
            });
        }
        if (btnRegen) {
            btnRegen.addEventListener('click', (e) => {
                e.stopPropagation();
                regenerateResponse();
            });
        }

        function updateResponseLayout() {
            if (
                responsePill.classList.contains('hidden') ||
                !responseText.textContent.trim()
            ) {
                mainDashboard.classList.remove('expanded');
                return;
            }

            const style = window.getComputedStyle(responseText);
            const lineHeight = parseFloat(style.lineHeight) || 23;

            const height = responseText.getBoundingClientRect().height;
            const lines = height / lineHeight;

            mainDashboard.classList.toggle(
                'expanded',
                lines > 3
            );
        }

        function showResponsePill(text, sources = [], usedWeb = false) {
            if (hideTimer) {
                clearTimeout(hideTimer);
                hideTimer = null;
            }

            const response = String(text || '');

            responsePill.classList.remove('hidden');

            try {
                if (window.marked && typeof window.marked.parse === 'function') {
                    const html = window.marked.parse(response);

                    if (window.DOMPurify && typeof window.DOMPurify.sanitize === 'function') {
                        responseText.innerHTML = window.DOMPurify.sanitize(html);
                    } else {
                        responseText.innerHTML = html;
                    }
                } else {
                    responseText.textContent = response;
                }
            } catch (error) {
                console.error('Markdown rendering failed:', error);
                responseText.textContent = response;
            }

            // Render subtle glassmorphism sources if web search was used AND sources exist
            const responseSources = document.getElementById('response-sources');
            if (responseSources) {
                if (usedWeb && Array.isArray(sources) && sources.length > 0) {
                    let chipsHtml = '<span class="sources-title">Sources:</span>';
                    sources.forEach(src => {
                        const url = String(src.url || '').trim();
                        if (url.startsWith('http://') || url.startsWith('https://')) {
                            const title = String(src.title || url).trim();
                            chipsHtml += `<a class="source-chip" href="${url}" target="_blank" rel="noopener noreferrer" title="${title}">${title}</a>`;
                        }
                    });
                    responseSources.innerHTML = chipsHtml;
                    responseSources.classList.remove('hidden');
                } else {
                    responseSources.innerHTML = '';
                    responseSources.classList.add('hidden');
                }
            }

            responsePill.scrollTop = 0;

            // ONLY AFTER THE RESPONSE IS DISPLAYED:
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    updateResponseLayout();
                });
            });

            hideTimer = setTimeout(() => {
                responsePill.classList.add('hidden');
                mainDashboard.classList.remove('expanded');
            }, 45000);
        }

        async function sendChat() {
            if (!chatInput) return;
            const text = chatInput.value.trim();
            if (!text) return;

            lastUserPrompt = text;

            chatInput.value = '';
            chatInput.disabled = true;
            chatSendBtn.disabled = true;

            // Hide previous response pill while processing new input
            if (responsePill) {
                responsePill.classList.add('hidden');
                mainDashboard.classList.remove('expanded');
            }

            // Start smooth, subtle white pulse glow on the word "FRIDAY" inside center box
            if (fridayText) {
                fridayText.classList.add('pulsing');
            }

            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({text: text})
                });
                const data = await res.json();
                lastResponseText = data.response || 'No response.';
                showResponsePill(lastResponseText, data.sources || [], data.used_web || false);
            } catch(e) {
                showResponsePill('Error: ' + e.message);
            } finally {
                // Stop pulse glow when response arrives
                if (fridayText) {
                    fridayText.classList.remove('pulsing');
                }
                chatInput.disabled = false;
                chatSendBtn.disabled = false;
                chatInput.focus();
            }
        }

        if (chatInput) {
            chatInput.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') { e.preventDefault(); sendChat(); }
            });
        }
        if (chatSendBtn) {
            chatSendBtn.addEventListener('click', function(e) { e.preventDefault(); sendChat(); });
        }

        if (btnPower && powerDropdown) {
            btnPower.addEventListener('click', (e) => {
                e.stopPropagation();
                powerDropdown.classList.toggle('active');
            });

            document.addEventListener('click', (e) => {
                if (!powerDropdown.contains(e.target) && !btnPower.contains(e.target)) {
                    powerDropdown.classList.remove('active');
                }
            });
        }

        if (btnShutdown) {
            btnShutdown.addEventListener('click', async () => {
                if (powerDropdown) powerDropdown.classList.remove('active');
                try {
                    await fetch('/api/power/shutdown', { method: 'POST' });
                    document.body.innerHTML = `
                        <div style="height:100vh; display:flex; flex-direction:column; justify-content:center; align-items:center; background:#030407; color:#ff5252; font-family:'Orbitron',sans-serif;">
                            <h1 style="font-size:32px; margin-bottom:12px;">🔴 FRIDAY SHUTDOWN</h1>
                            <p style="color:#94a3b8; font-size:15px;">Process terminated successfully. You can close this tab.</p>
                        </div>
                    `;
                } catch (e) {
                    console.error(e);
                }
            });
        }

        if (btnRestart) {
            btnRestart.addEventListener('click', () => {
                if (powerDropdown) powerDropdown.classList.remove('active');
                alert('Restart (Friday) is currently held as a placeholder.');
            });
        }

        if (btnUpdate) {
            btnUpdate.addEventListener('click', async () => {
                if (powerDropdown) powerDropdown.classList.remove('active');
                try {
                    document.body.innerHTML = `
                        <div style="height:100vh; display:flex; flex-direction:column; justify-content:center; align-items:center; background:#030407; color:#00f2fe; font-family:'Orbitron',sans-serif;">
                            <h1 style="font-size:32px; margin-bottom:12px;">🔄 RELOADING FRIDAY...</h1>
                            <p style="color:#94a3b8; font-size:15px;">Applying updates and restarting system process...</p>
                        </div>
                    `;
                    await fetch('/api/power/update', { method: 'POST' });
                    setTimeout(() => {
                        window.location.reload();
                    }, 2000);
                } catch (e) {
                    console.error(e);
                }
            });
        }

        if (btnSettings && settingsBackdrop) {
            btnSettings.addEventListener('click', () => {
                if (powerDropdown) powerDropdown.classList.remove('active');
                settingsBackdrop.classList.add('active');
            });
        }

        if (btnCloseSettings && settingsBackdrop) {
            btnCloseSettings.addEventListener('click', () => {
                settingsBackdrop.classList.remove('active');
            });

            settingsBackdrop.addEventListener('click', (e) => {
                if (e.target === settingsBackdrop) {
                    settingsBackdrop.classList.remove('active');
                }
            });
        }
    </script>
</body>
</html>
"""


@app.get("/")
async def get_dashboard():
    return HTMLResponse(content=DASHBOARD_HTML)


@app.get("/api/status")
async def get_status():
    soul = read_soul_profile()
    apps_data = load_known_apps()
    total_apps = apps_data.get("_meta", {}).get("total_apps", 0)

    return {
        "cpu": round(psutil.cpu_percent(), 1),
        "ram": round(psutil.virtual_memory().percent, 1),
        "stage_name": STAGE_LABELS.get(soul.get("stage", 0), "Stranger"),
        "sessions": soul.get("sessions_together", 0),
        "total_apps": total_apps,
        "github_token": get_github_token(),
        "groq_key": get_groq_key(),
        "tg_token": get_telegram_token(),
        "whitelisted_users": ",".join(map(str, get_authorized_user_ids()))
    }


@app.post("/api/chat")
async def post_chat(payload: dict = Body(...)):
    text = payload.get("text", "").strip() if isinstance(payload, dict) else ""
    if not text:
        return {
            "response": "Please enter a valid message.",
            "sources": [],
            "used_web": False,
            "web_requested": False,
            "web_failed": False
        }
    
    try:
        meta = await asyncio.wait_for(
            asyncio.to_thread(process_user_input_with_metadata, text),
            timeout=30.0
        )
        return meta
    except asyncio.TimeoutError:
        logger.error("⚠️ /api/chat request timed out after 30 seconds")
        return {
            "response": "FRIDAY couldn't complete that request because the AI service timed out.",
            "sources": [],
            "used_web": False,
            "web_requested": True,
            "web_failed": True
        }
    except Exception as e:
        logger.error(f"❌ /api/chat error: {e}")
        return {
            "response": f"FRIDAY encountered an error: {e}",
            "sources": [],
            "used_web": False,
            "web_requested": False,
            "web_failed": True
        }


@app.post("/api/config")
async def post_config(payload: dict = Body(...)):
    save_env_values(
        github_token=payload.get("github_token", "").strip(),
        groq_key=payload.get("groq_key", "").strip(),
        tg_token=payload.get("tg_token", "").strip(),
        user_ids=payload.get("user_ids", "").strip()
    )
    return {"message": "Settings saved to .env successfully!"}


@app.post("/api/power/shutdown")
async def power_shutdown():
    """Terminates the Python process completely (equivalent to terminal exit)."""
    def shutdown_process():
        os._exit(0)
    threading.Timer(0.4, shutdown_process).start()
    return {"message": "Friday process terminated."}


@app.post("/api/power/update")
async def power_update():
    """Restarts the Python process with updated code files from disk."""
    def reload_process():
        python = sys.executable
        os.execl(python, python, *sys.argv)
    threading.Timer(0.5, reload_process).start()
    return {"message": "Reloading Friday process with latest updates..."}


def start_dashboard_in_background(open_browser: bool = True) -> str:
    """Launches the Uvicorn FastAPI server in a background daemon thread."""
    global server_thread
    url = f"http://localhost:{WEBRTC_PORT}"

    if server_thread is None or not server_thread.is_alive():
        def run_server():
            config = uvicorn.Config(app=app, host="0.0.0.0", port=WEBRTC_PORT, log_level="error")
            server = uvicorn.Server(config)
            server.run()

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

    if open_browser:
        webbrowser.open(url)

    return url
