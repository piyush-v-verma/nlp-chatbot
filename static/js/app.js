/**
 * NLP Chatbot Application JS Controller
 * Preserves existing UI design and layout while integrating Speech and JSON formatting.
 */

document.addEventListener('DOMContentLoaded', () => {
    // State Variables
    let activeChatId = null;
    let chats = [];
    let selectedNlpData = null; // Inspections data cache
    let autocompleteSelectedIdx = -1;
    let autocompleteSuggestions = [];
    let debounceTimer = null;
    let isExpanded = false;

    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    // DOM Elements
    const bodyEl = document.body;
    const sidebarLeft = document.getElementById('sidebar-left');
    const sidebarRight = document.getElementById('sidebar-right');
    const messagesContainer = document.getElementById('messages-container');
    const chatInput = document.getElementById('chat-input');
    const expandToggleBtn = document.getElementById('expand-toggle-btn');
    const sendBtn = document.getElementById('send-btn');
    const micBtn = document.getElementById('mic-btn');
    const activeChatTitle = document.getElementById('active-chat-title');
    const chatList = document.getElementById('chat-list');
    
    // Buttons
    const newChatBtn = document.getElementById('new-chat-btn');
    const hideSidebarBtn = document.getElementById('hide-sidebar-btn');
    const showSidebarBtn = document.getElementById('show-sidebar-btn');
    const inspectorToggleBtn = document.getElementById('inspector-toggle-btn');
    const closeInspectorBtn = document.getElementById('close-inspector-btn');
    
    // Autocomplete & Welcome panel
    const autocompletePopup = document.getElementById('autocomplete-popup');
    const welcomeScreen = document.getElementById('welcome-screen');
    
    // Inspector DOM
    const inspectorBanner = document.getElementById('inspector-banner');
    const inspectorContent = document.getElementById('inspector-content');
    const inspectorSourceText = document.getElementById('inspector-source-text');
    const inspectorLatencyText = document.getElementById('inspector-latency-text');
    const statTokenCount = document.getElementById('stat-token-count');
    const statIntentBadge = document.getElementById('stat-intent-badge');
    const badgeTokensCount = document.getElementById('badge-tokens-count');
    const badgeNerCount = document.getElementById('badge-ner-count');
    const tokenStatsBar = document.getElementById('token-stats-bar');
    const countRawTokens = document.getElementById('count-raw-tokens');
    const countCleanTokens = document.getElementById('count-clean-tokens');
    const countStemmedTokens = document.getElementById('count-stemmed-tokens');
    const nerHighlightedBox = document.getElementById('ner-highlighted-box');
    const pipelineFlowchart = document.getElementById('pipeline-flowchart');
    
    const tokensListRaw = document.getElementById('tokens-list-raw');
    const tokensListClean = document.getElementById('tokens-list-clean');
    const tokensListStemmed = document.getElementById('tokens-list-stemmed');
    
    const posTagsList = document.getElementById('pos-tags-list');
    const chunkTreeVisual = document.getElementById('chunk-tree-visual');
    
    const nerTableBody = document.getElementById('ner-table-body');
    const noNerMessage = document.getElementById('no-ner-message');
    
    const ldaHasData = document.getElementById('lda-has-data');
    const ldaTopicsList = document.getElementById('lda-topics-list');
    const ldaSentencesList = document.getElementById('lda-sentences-list');
    const noLdaMessage = document.getElementById('no-lda-message');

    /* ==========================================================================
       Speech APIs Configuration (Web Speech API)
       ========================================================================== */
    let recognition = null;
    let isRecording = false;
    
    // 1. Initialize Speech-to-Text (STT)
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US'; // Default locale
        
        recognition.onstart = () => {
            isRecording = true;
            micBtn.classList.add('active');
            micBtn.title = "Listening... Click to stop";
            chatInput.placeholder = "Listening... Speak clearly into your microphone.";
        };
        
        recognition.onend = () => {
            isRecording = false;
            micBtn.classList.remove('active');
            micBtn.title = "Speech to Text (Microphone)";
            chatInput.placeholder = "Type a message or ask an NLP question naturally...";
        };
        
        recognition.onresult = (event) => {
            const resultText = event.results[0][0].transcript;
            const prevText = chatInput.value.trim();
            // Append transcribed words cleanly
            chatInput.value = prevText ? prevText + " " + resultText : resultText;
            chatInput.focus();
            adjustTextareaHeight();
            validateInput();
        };
        
        recognition.onerror = (event) => {
            console.error("Speech capture error:", event.error);
            isRecording = false;
            micBtn.classList.remove('active');
            
            if (event.error === 'not-allowed') {
                alert("Microphone access is blocked! Please click the camera/microphone icon in your browser's address bar to grant microphone permissions for this website.");
            } else if (event.error === 'no-speech') {
                alert("No speech was detected. Please verify your microphone is connected and speak clearly.");
            } else if (event.error === 'network') {
                alert("Speech recognition network error. Please verify your internet connection and try again.");
            }
        };
        
        micBtn.addEventListener('click', () => {
            if (isRecording) {
                recognition.stop();
            } else {
                // Request user media to wake up the Bluetooth audio device and trigger permission prompt
                if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                    navigator.mediaDevices.getUserMedia({ audio: true })
                    .then(stream => {
                        // Stop the stream tracks immediately to release the device for SpeechRecognition
                        stream.getTracks().forEach(track => track.stop());
                        try {
                            recognition.start();
                        } catch (e) {
                            console.error("Failed to start speech recognition:", e);
                        }
                    })
                    .catch(err => {
                        console.error("Microphone access denied or error:", err);
                        alert("Could not access microphone. Please ensure permissions are granted and your buds are connected.");
                    });
                } else {
                    // Fallback if mediaDevices not available (e.g. non-secure origin)
                    try {
                        recognition.start();
                    } catch (e) {
                        console.error("Failed to start speech recognition:", e);
                    }
                }
            }
        });
    } else {
        // Fallback: hide mic button if Web Speech API is not supported in client browser
        micBtn.style.display = 'none';
    }

    // 2. Initialize Text-to-Speech (TTS)
    function speakText(text) {
        if ('speechSynthesis' in window) {
            // Stop any ongoing voice readings
            window.speechSynthesis.cancel();
            
            if (!text) return;
            
            // Clean text of markdown formatting before speaking
            const cleanText = text.replace(/\*\*|`|#/g, '');
            const utterance = new SpeechSynthesisUtterance(cleanText);
            
            // Automatic script detection to route English/Hindi engines correctly
            const containsHindi = /[\u0900-\u097F]/.test(cleanText);
            utterance.lang = containsHindi ? 'hi-IN' : 'en-US';
            
            // Try to match system voice
            const voices = window.speechSynthesis.getVoices();
            if (voices.length > 0) {
                const voice = voices.find(v => v.lang.startsWith(containsHindi ? 'hi' : 'en'));
                if (voice) {
                    utterance.voice = voice;
                }
            }
            
            window.speechSynthesis.speak(utterance);
        } else {
            console.warn("speechSynthesis is not supported in this browser.");
        }
    }

    // Pre-load speech voices for compatibility
    if ('speechSynthesis' in window) {
        window.speechSynthesis.getVoices();
    }

    /* ==========================================================================
       Initialization
       ========================================================================== */
    function init() {
        loadSavedAppearance();
        const savedChatId = localStorage.getItem('activeChatId');
        if (savedChatId) {
            selectChat(savedChatId);
            fetchChats(false);
        } else {
            createNewChat();
        }
        newChatBtn.addEventListener('click', createNewChat);
        hideSidebarBtn.addEventListener('click', () => toggleLeftSidebar(true));
        showSidebarBtn.addEventListener('click', () => toggleLeftSidebar(false));
        inspectorToggleBtn.addEventListener('click', () => toggleRightInspector());
        closeInspectorBtn.addEventListener('click', () => toggleRightInspector(true));
        if (expandToggleBtn) {
            expandToggleBtn.addEventListener('click', () => {
                isExpanded = !isExpanded;
                if (isExpanded) {
                    expandToggleBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-minimize-2"><polyline points="4 14 10 14 10 20"></polyline><polyline points="20 10 14 10 14 4"></polyline><line x1="14" y1="10" x2="21" y2="3"></line><line x1="10" y1="14" x2="3" y2="20"></line></svg>`;
                    expandToggleBtn.title = "Minimize input";
                } else {
                    expandToggleBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-maximize-2"><polyline points="15 3 21 3 21 9"></polyline><polyline points="9 21 3 21 3 15"></polyline><line x1="21" y1="3" x2="14" y2="10"></line><line x1="3" y1="21" x2="10" y2="14"></line></svg>`;
                    expandToggleBtn.title = "Expand input";
                }
                adjustTextareaHeight();
            });
        }
        
        chatInput.addEventListener('input', handleInput);
        chatInput.addEventListener('keydown', handleKeyDown);
        sendBtn.addEventListener('click', submitMessage);
        
        const copyNlpJsonBtn = document.getElementById('copy-nlp-json-btn');
        if (copyNlpJsonBtn) {
            copyNlpJsonBtn.addEventListener('click', () => {
                if (!selectedNlpData) return;
                const jsonStr = JSON.stringify(selectedNlpData, null, 2);
                navigator.clipboard.writeText(jsonStr).then(() => {
                    const origHtml = copyNlpJsonBtn.innerHTML;
                    copyNlpJsonBtn.innerHTML = '<i class="fa-solid fa-check" style="color: #a6e3a1;"></i>';
                    setTimeout(() => {
                        copyNlpJsonBtn.innerHTML = origHtml;
                    }, 1500);
                }).catch(err => console.error("Clipboard copy error:", err));
            });
        }
        
        const inspectorTabsContainer = document.querySelector('.inspector-tabs');
        if (inspectorTabsContainer) {
            let isDown = false;
            let startX;
            let scrollLeft;
            let hasDragged = false;

            inspectorTabsContainer.addEventListener('mousedown', (e) => {
                isDown = true;
                hasDragged = false;
                inspectorTabsContainer.classList.add('active-dragging');
                startX = e.pageX - inspectorTabsContainer.offsetLeft;
                scrollLeft = inspectorTabsContainer.scrollLeft;
            });

            inspectorTabsContainer.addEventListener('mouseleave', () => {
                isDown = false;
                inspectorTabsContainer.classList.remove('active-dragging');
            });

            inspectorTabsContainer.addEventListener('mouseup', () => {
                isDown = false;
                inspectorTabsContainer.classList.remove('active-dragging');
            });

            inspectorTabsContainer.addEventListener('mousemove', (e) => {
                if (!isDown) return;
                e.preventDefault();
                const x = e.pageX - inspectorTabsContainer.offsetLeft;
                const walk = (x - startX) * 1.5;
                if (Math.abs(walk) > 4) {
                    hasDragged = true;
                }
                inspectorTabsContainer.scrollLeft = scrollLeft - walk;
            });

            // Wheel horizontal sliding support
            inspectorTabsContainer.addEventListener('wheel', (e) => {
                if (e.deltaY !== 0) {
                    e.preventDefault();
                    inspectorTabsContainer.scrollLeft += e.deltaY;
                }
            }, { passive: false });

            // On tab click, handle selection and smooth view alignment
            document.querySelectorAll('.inspector-tabs .tab-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    if (hasDragged) {
                        e.preventDefault();
                        e.stopPropagation();
                        hasDragged = false;
                        return;
                    }
                    const targetBtn = e.currentTarget;
                    switchTab(targetBtn.getAttribute('data-tab'));
                });
            });
        }
        
        document.querySelectorAll('.capability-card').forEach(card => {
            card.addEventListener('click', () => {
                chatInput.value = card.getAttribute('data-cmd');
                chatInput.focus();
                adjustTextareaHeight();
                validateInput();
            });
        });

        document.querySelectorAll('.prompt-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                chatInput.value = chip.getAttribute('data-prompt');
                chatInput.focus();
                adjustTextareaHeight();
                validateInput();
            });
        });
        
        document.addEventListener('click', (e) => {
            if (!autocompletePopup.contains(e.target) && e.target !== chatInput) {
                hideAutocomplete();
            }
        });
        
        if (window.innerWidth <= 1024) {
            toggleLeftSidebar(true);
            toggleRightInspector(true);
        } else {
            toggleRightInspector(true);
        }
        
        initSidebarResizers();

        window.addEventListener('resize', updateScrollClearance);
        updateScrollClearance();
    }

    /* ==========================================================================
       Interactive Sidebar Drag-to-Resize & Persistence
       ========================================================================== */
    function initSidebarResizers() {
        const leftResizer = document.getElementById('sidebar-left-resizer');
        const rightResizer = document.getElementById('sidebar-right-resizer');
        
        // 1. Restore saved custom widths from localStorage if previously resized by user
        const savedLeftWidth = localStorage.getItem('x_pilot_sidebar_left_width');
        if (savedLeftWidth) {
            const parsedLeft = parseInt(savedLeftWidth, 10);
            if (!isNaN(parsedLeft) && parsedLeft >= 180 && parsedLeft <= 600) {
                document.documentElement.style.setProperty('--sidebar-left-width', `${parsedLeft}px`);
            }
        }

        const savedRightWidth = localStorage.getItem('x_pilot_sidebar_right_width');
        if (savedRightWidth) {
            const parsedRight = parseInt(savedRightWidth, 10);
            if (!isNaN(parsedRight) && parsedRight >= 260 && parsedRight <= 800) {
                document.documentElement.style.setProperty('--sidebar-right-width', `${parsedRight}px`);
            }
        }

        // 2. Dragging state variables
        let isResizingLeft = false;
        let isResizingRight = false;

        // Left Sidebar Resizer Handlers
        if (leftResizer) {
            const startLeftResize = (e) => {
                if (sidebarLeft.classList.contains('collapsed')) return;
                isResizingLeft = true;
                document.body.classList.add('is-resizing');
                leftResizer.classList.add('is-active-dragging');
            };

            leftResizer.addEventListener('mousedown', startLeftResize);
            leftResizer.addEventListener('touchstart', startLeftResize, { passive: true });
        }

        // Right Sidebar Resizer Handlers
        if (rightResizer) {
            const startRightResize = (e) => {
                if (sidebarRight.classList.contains('collapsed')) return;
                isResizingRight = true;
                document.body.classList.add('is-resizing');
                rightResizer.classList.add('is-active-dragging');
            };

            rightResizer.addEventListener('mousedown', startRightResize);
            rightResizer.addEventListener('touchstart', startRightResize, { passive: true });
        }

        // Global Move & End Handlers
        const onPointerMove = (e) => {
            if (!isResizingLeft && !isResizingRight) return;
            
            const clientX = e.touches && e.touches.length > 0 ? e.touches[0].clientX : e.clientX;
            if (clientX === undefined) return;

            if (isResizingLeft) {
                const minWidth = 180;
                const maxWidth = Math.min(600, Math.floor(window.innerWidth * 0.5));
                const newWidth = Math.max(minWidth, Math.min(clientX, maxWidth));
                document.documentElement.style.setProperty('--sidebar-left-width', `${newWidth}px`);
            } else if (isResizingRight) {
                const minWidth = 260;
                const maxWidth = Math.min(800, Math.floor(window.innerWidth * 0.6));
                const newWidth = Math.max(minWidth, Math.min(window.innerWidth - clientX, maxWidth));
                document.documentElement.style.setProperty('--sidebar-right-width', `${newWidth}px`);
            }
        };

        const onPointerUp = () => {
            if (isResizingLeft) {
                isResizingLeft = false;
                document.body.classList.remove('is-resizing');
                if (leftResizer) leftResizer.classList.remove('is-active-dragging');
                
                const curWidth = getComputedStyle(document.documentElement).getPropertyValue('--sidebar-left-width').trim();
                if (curWidth) localStorage.setItem('x_pilot_sidebar_left_width', parseInt(curWidth, 10));
            }

            if (isResizingRight) {
                isResizingRight = false;
                document.body.classList.remove('is-resizing');
                if (rightResizer) rightResizer.classList.remove('is-active-dragging');
                
                const curWidth = getComputedStyle(document.documentElement).getPropertyValue('--sidebar-right-width').trim();
                if (curWidth) localStorage.setItem('x_pilot_sidebar_right_width', parseInt(curWidth, 10));
            }
        };

        window.addEventListener('mousemove', onPointerMove, { passive: false });
        window.addEventListener('touchmove', onPointerMove, { passive: false });
        window.addEventListener('mouseup', onPointerUp);
        window.addEventListener('touchend', onPointerUp);
    }

    /* ==========================================================================
       UI Toggles & Theme
       ========================================================================== */
    function toggleLeftSidebar(collapse) {
        if (collapse === undefined) sidebarLeft.classList.toggle('collapsed');
        else if (collapse) sidebarLeft.classList.add('collapsed');
        else sidebarLeft.classList.remove('collapsed');
    }

    function toggleRightInspector(collapse) {
        if (collapse === undefined) sidebarRight.classList.toggle('collapsed');
        else if (collapse) sidebarRight.classList.add('collapsed');
        else sidebarRight.classList.remove('collapsed');
        
        // Hide or show the Inspect NLP button based on sidebarRight collapsed state
        if (sidebarRight.classList.contains('collapsed')) {
            inspectorToggleBtn.style.display = 'flex';
        } else {
            inspectorToggleBtn.style.display = 'none';
        }
    }

    function switchTab(tabId) {
        document.querySelectorAll('.inspector-tabs .tab-btn').forEach(btn => {
            if (btn.getAttribute('data-tab') === tabId) {
                btn.classList.add('active');
                btn.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
            } else {
                btn.classList.remove('active');
            }
        });
        
        document.querySelectorAll('.tab-panels .tab-panel').forEach(panel => {
            if (panel.id === tabId) panel.classList.add('active');
            else panel.classList.remove('active');
        });
    }

    /* ==========================================================================
       Database Loading / Sessions
       ========================================================================== */
    function fetchChats(selectFirst = false) {
        fetch('/api/chats')
            .then(res => res.json())
            .then(data => {
                chats = data;
                renderChatList();
                
                if (selectFirst && chats.length > 0) {
                    selectChat(chats[0].id);
                } else if (chats.length === 0) {
                    showWelcome();
                }
            })
            .catch(err => console.error("Error loading chat logs list:", err));
    }

    function renderChatList() {
        chatList.innerHTML = '';
        chats.forEach(chat => {
            // Do not show empty chats in history sidebar until they have messages
            if (!chat.last_message) {
                return;
            }
            const li = document.createElement('li');
            li.className = `chat-item ${chat.id === activeChatId ? 'active' : ''}`;
            li.setAttribute('data-id', chat.id);
            li.addEventListener('click', () => selectChat(chat.id));
            
            li.innerHTML = `
                <div class="chat-item-content">
                    <i class="fa-regular fa-comment"></i>
                    <div class="chat-item-title" title="${chat.title}">${chat.title}</div>
                </div>
                <button class="chat-item-delete" title="Delete Chat Log">
                    <i class="fa-regular fa-trash-can"></i>
                </button>
            `;
            
            const delBtn = li.querySelector('.chat-item-delete');
            delBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteChat(chat.id);
            });
            
            chatList.appendChild(li);
        });
    }

    function createNewChat() {
        // If there's already an active empty chat, reuse it rather than creating a new one
        if (activeChatId && messagesContainer.querySelectorAll('.message-row').length === 0) {
            chatInput.focus();
            return;
        }

        fetch('/api/chats', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            }
        })
        .then(res => res.json())
        .then(chat => {
            activeChatId = chat.id;
            activeChatTitle.textContent = chat.title;
            clearMessagesFeed();
            showWelcome();
            fetchChats(false);
            chatInput.focus();
        })
        .catch(err => console.error("Error creating chat:", err));
    }

    function deleteChat(chatId) {
        showCustomConfirm(
            "Delete Chat Session",
            "Are you sure you want to delete this chat session? This will permanently delete all message history.",
            () => {
                fetch(`/api/chats/${chatId}`, { 
                    method: 'DELETE',
                    headers: {
                        'X-CSRFToken': getCsrfToken()
                    }
                })
                .then(res => res.json())
                .then(() => {
                    if (activeChatId === chatId) {
                        activeChatId = null;
                        localStorage.removeItem('activeChatId');
                        clearMessagesFeed();
                        showWelcome();
                        activeChatTitle.textContent = "New Chat";
                        inspectorBanner.style.display = 'flex';
                        inspectorContent.style.display = 'none';
                    }
                    fetchChats(false);
                })
                .catch(err => console.error("Error deleting chat:", err));
            }
        );
    }

    function selectChat(chatId) {
        // If we are switching away from an empty active chat, silently delete it
        if (activeChatId && activeChatId !== chatId && messagesContainer.querySelectorAll('.message-row').length === 0) {
            const emptyChatId = activeChatId;
            fetch(`/api/chats/${emptyChatId}`, { 
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': getCsrfToken()
                }
            })
            .then(() => fetchChats(false))
            .catch(err => console.error("Error clearing empty chat on leave:", err));
        }

        activeChatId = chatId;
        localStorage.setItem('activeChatId', chatId);
        
        document.querySelectorAll('.chat-list .chat-item').forEach(item => {
            if (item.getAttribute('data-id') === chatId) item.classList.add('active');
            else item.classList.remove('active');
        });
        
        const chat = chats.find(c => c.id === chatId);
        if (chat) {
            activeChatTitle.textContent = chat.title;
        } else {
            activeChatTitle.textContent = "New Chat";
        }
        
        clearMessagesFeed();
        
        fetch(`/api/chats/${chatId}/messages`)
            .then(res => {
                if (!res.ok) {
                    localStorage.removeItem('activeChatId');
                    fetchChats(true);
                    throw new Error("Chat session not found on server");
                }
                return res.json();
            })
            .then(messages => {
                if (messages.length === 0) {
                    showWelcome();
                } else {
                    welcomeScreen.style.display = 'none';
                    messages.forEach(msg => appendMessageBubble(msg));
                    updateScrollClearance();
                    scrollToBottom();
                }
            })
            .catch(err => console.warn("Error loading messages:", err));
    }

    /* ==========================================================================
       Message Feed Rendering (Renders JSON structured formats dynamically)
       ========================================================================== */
    function clearMessagesFeed() {
        const rows = messagesContainer.querySelectorAll('.message-row, .typing-indicator-row');
        rows.forEach(r => r.remove());
    }

    function showWelcome() {
        welcomeScreen.style.display = 'block';
        const endFooter = document.getElementById('chat-end-footer');
        if (endFooter) endFooter.style.display = 'none';
    }

    function appendMessageBubble(msg) {
        welcomeScreen.style.display = 'none';
        const endFooter = document.getElementById('chat-end-footer');
        if (endFooter) endFooter.style.display = 'flex';
        
        const row = document.createElement('div');
        row.className = `message-row ${msg.role}`;
        
        const avatarHtml = msg.role === 'user' 
            ? `<div class="avatar user-avatar"><i class="fa-regular fa-user"></i></div>`
            : `<div class="avatar bot-avatar"><i class="fa-solid fa-robot"></i></div>`;
            
        let bodyHtml = "";
        let actionsHtml = "";
        let textToSpeak = "";
        
        if (msg.role === 'user') {
            bodyHtml = `<p>${parseMarkdown(msg.content)}</p>`;
            textToSpeak = msg.content;
        } else {
            // Assistant response bubble parsing
            try {
                // Parse structured JSON returned by ResponseFormatter
                const resData = JSON.parse(msg.content);
                const type = resData.type;
                const title = resData.title;
                const confidence = resData.confidence;
                const explanation = resData.explanation;
                const data = resData.data;
                
                // 1. NLP Module Badge
                const moduleNameMap = {
                    "sentiment": "Sentiment Analysis",
                    "translation": "Translation",
                    "ner": "Named Entity Recognition",
                    "pos": "POS Tagging",
                    "summarize": "Summarization",
                    "wikipedia": "Wikipedia Search",
                    "general": "General Conversation",
                    "error": "System Error",
                    "chunk": "Syntax Chunking",
                    "topic": "LDA Topic Modeling"
                };
                const moduleBadge = moduleNameMap[type] || "NLP Engine";
                bodyHtml += `<div class="message-module-badge">Module: ${moduleBadge}</div>`;
                
                // 2. Structured Body Layouts
                if (type === "sentiment") {
                    const emoji = data.label.toLowerCase() === "positive" ? "😊" : (data.label.toLowerCase() === "negative" ? "😠" : "😐");
                    bodyHtml += `
                        <h4 style="margin-bottom:6px;">${title} ${emoji}</h4>
                        <p><strong>Sentiment polarity:</strong> <code>${data.label}</code></p>
                        <p><strong>VADER Score:</strong> <code>${data.compound.toFixed(4)}</code> (Confidence: ${Math.round(confidence * 100)}%)</p>
                        <p style="margin-top:8px; font-size:0.9rem; color:var(--text-muted);">${explanation}</p>
                    `;
                    textToSpeak = `${data.label} sentiment. ${explanation}`;
                } 
                else if (type === "translation") {
                    bodyHtml += `
                        <h4 style="margin-bottom:6px;">${title}</h4>
                        <p style="font-size:0.75rem; color:var(--text-muted); margin-bottom:8px;">Detected Language: <strong>${data.source_lang}</strong></p>
                        <p style="font-size:1.1rem; color:var(--accent); font-weight:500; margin:10px 0;">${data.translated}</p>
                        <p style="font-size:0.8rem; font-style:italic; opacity:0.8;">Original: "${data.original}"</p>
                    `;
                    textToSpeak = data.translated;
                }
                else if (type === "ner") {
                    const listItems = data.map(ent => `<li><strong>${ent.text}</strong> — <code style="font-size:0.75rem;">${ent.label}</code></li>`).join('');
                    bodyHtml += `
                        <h4 style="margin-bottom:6px;">${title}</h4>
                        <ul style="padding-left:18px; margin:8px 0;">${listItems || '<li>No named entities recognized.</li>'}</ul>
                        <p style="font-size:0.9rem; color:var(--text-muted);">${explanation}</p>
                    `;
                    textToSpeak = `Named entities found: ` + data.map(ent => ent.text).join(', ');
                }
                else if (type === "pos") {
                    const cards = data.map(item => `
                        <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border-color); padding:4px 8px; border-radius:6px; text-align:center; min-width:80px;">
                            <span style="font-family:var(--font-mono); font-size:0.85rem; font-weight:600;">${item.word}</span>
                            <div style="font-size:0.7rem; color:var(--accent); margin-top:2px;" title="${item.meaning}">${item.tag}</div>
                        </div>
                    `).join('');
                    bodyHtml += `
                        <h4 style="margin-bottom:6px;">${title}</h4>
                        <div style="display:flex; flex-wrap:wrap; gap:6px; margin:10px 0;">${cards}</div>
                        <p style="font-size:0.85rem; color:var(--text-muted);">${explanation}</p>
                    `;
                    textToSpeak = `Part of speech tagged. Input has ${data.length} tokens.`;
                }
                else if (type === "summarize") {
                    bodyHtml += `
                        <h4 style="margin-bottom:6px;">${title}</h4>
                        <p style="font-style:italic; border-left:3px solid var(--accent); padding-left:10px; margin:10px 0; line-height:1.55;">"${data.summary}"</p>
                        <p style="font-size:0.85rem; color:var(--text-muted);">${explanation}</p>
                    `;
                    textToSpeak = data.summary;
                }
                else if (type === "wikipedia") {
                    bodyHtml += `
                        <h4 style="margin-bottom:6px;">${title}</h4>
                        <p style="margin-bottom:10px; line-height:1.5;">${data.extract}</p>
                        <p><a href="${data.url}" target="_blank" rel="noopener noreferrer" style="font-size:0.85rem; text-decoration:underline;">Read more on Wikipedia <i class="fa-solid fa-up-right-from-square" style="font-size:0.75em;"></i></a></p>
                    `;
                    textToSpeak = data.extract;
                }
                else if (type === "math") {
                    bodyHtml += `
                        <h4 style="margin-bottom:6px;">${title} 🧮</h4>
                        <p><strong>Operation:</strong> ${data.operation || 'Math Solver'}</p>
                        <p style="font-size:1.15rem; color:var(--accent); font-weight:600; margin:10px 0;">Result: ${data.result}</p>
                        <p style="font-size:0.85rem; color:var(--text-muted); font-family:var(--font-mono); background:rgba(0,0,0,0.15); padding:6px 10px; border-radius:6px; margin-top:8px;">${data.steps}</p>
                    `;
                    textToSpeak = `Math solver evaluated the expression to ${data.result}`;
                }
                else if (type === "general") {
                    bodyHtml += `
                        <p>${parseMarkdown(data.response)}</p>
                    `;
                    textToSpeak = data.response;
                }
                else if (type === "error") {
                    bodyHtml += `
                        <p style="color:var(--error); font-weight:500;"><i class="fa-solid fa-triangle-exclamation"></i> <strong>${title}:</strong> ${data.error_message}</p>
                    `;
                    textToSpeak = data.error_message;
                }
                else if (type === "chunk" || type === "topic") {
                    // Custom non-formatted tabs
                    bodyHtml += `
                        <h4 style="margin-bottom:6px;">${title}</h4>
                        <p style="margin-bottom:10px;">${explanation}</p>
                        <p style="font-size:0.85rem; color:var(--text-muted);"><i class="fa-solid fa-circle-info"></i> Click the <strong>Inspect NLP</strong> button below to inspect POS chunk trees or LDA distribution graphs in detail.</p>
                    `;
                    textToSpeak = explanation;
                }
                
            } catch (jsonErr) {
                // Fallback rendering if content isn't JSON formatted
                bodyHtml = `<p>${parseMarkdown(msg.content)}</p>`;
                textToSpeak = msg.content;
            }
            
            // Build action buttons (Listen / Inspect)
            if (msg.nlp_analysis) {
                const sentiment = msg.nlp_analysis.sentiment;
                let sentimentLabel = 'Neutral';
                let sentimentClass = 'neutral';
                let sentimentIcon = 'fa-circle';
                
                if (sentiment && sentiment.label) {
                    sentimentLabel = sentiment.label.charAt(0).toUpperCase() + sentiment.label.slice(1);
                    sentimentClass = sentiment.label.toLowerCase();
                    if (sentimentClass === 'positive') sentimentIcon = 'fa-face-smile';
                    if (sentimentClass === 'negative') sentimentIcon = 'fa-face-frown';
                }
                
                actionsHtml = `
                    <div class="message-actions">
                        <span class="sentiment-badge ${sentimentClass}">
                            <i class="fa-regular ${sentimentIcon}"></i> ${sentimentLabel}
                        </span>
                        <button class="inspect-msg-btn speak-msg-btn">
                            <i class="fa-solid fa-volume-high"></i> Listen
                        </button>
                        <button class="inspect-msg-btn nlp-inspect-trigger">
                            <i class="fa-solid fa-magnifying-glass-chart"></i> Inspect NLP
                        </button>
                    </div>
                `;
            }
        }
        
        row.innerHTML = `
            ${msg.role === 'bot' ? avatarHtml : ''}
            <div class="message-bubble-wrapper">
                <div class="message-bubble">
                    ${bodyHtml}
                </div>
                ${actionsHtml}
            </div>
            ${msg.role === 'user' ? avatarHtml : ''}
        `;
        
        // Bind TTS Speech Speaker button
        const speakBtn = row.querySelector('.speak-msg-btn');
        if (speakBtn) {
            speakBtn.addEventListener('click', () => {
                speakText(textToSpeak);
            });
        }
        
        // Bind Inspector Panel triggers
        const inspectBtn = row.querySelector('.nlp-inspect-trigger');
        if (inspectBtn) {
            inspectBtn.addEventListener('click', () => {
                inspectMessage(msg);
            });
        }
        
        messagesContainer.appendChild(row);
        if (endFooter) {
            messagesContainer.appendChild(endFooter);
        }
        const clearanceDiv = document.getElementById('chat-scroll-clearance');
        if (clearanceDiv) {
            messagesContainer.appendChild(clearanceDiv);
        }
    }

    function appendTypingIndicator() {
        const row = document.createElement('div');
        row.className = 'message-row bot typing-indicator-row';
        row.innerHTML = `
            <div class="avatar bot-avatar"><i class="fa-solid fa-robot"></i></div>
            <div class="message-bubble-wrapper">
                <div class="message-bubble">
                    <div class="typing-indicator">
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                    </div>
                </div>
            </div>
        `;
        messagesContainer.appendChild(row);
        const endFooter = document.getElementById('chat-end-footer');
        if (endFooter) {
            messagesContainer.appendChild(endFooter);
        }
        const clearanceDiv = document.getElementById('chat-scroll-clearance');
        if (clearanceDiv) {
            messagesContainer.appendChild(clearanceDiv);
        }
        scrollToBottom();
    }

    function removeTypingIndicator() {
        const indicator = messagesContainer.querySelector('.typing-indicator-row');
        if (indicator) indicator.remove();
    }

    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function parseMarkdown(text) {
        if (!text) return "";
        let html = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/`(.*?)`/g, '<code>$1</code>');
        html = html.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1 <i class="fa-solid fa-up-right-from-square" style="font-size:0.7em;"></i></a>');
        
        const lines = html.split('\n');
        let inList = false;
        const processedLines = lines.map(line => {
            const stripped = line.trim();
            if (stripped.startsWith('- ') || stripped.startsWith('* ')) {
                let content = stripped.slice(2);
                let prefix = '';
                if (!inList) {
                    prefix = '<ul>';
                    inList = true;
                }
                return `${prefix}<li>${content}</li>`;
            } else {
                let prefix = '';
                if (inList) {
                    prefix = '</ul>';
                    inList = false;
                }
                return `${prefix}${line}`;
            }
        });
        if (inList) processedLines.push('</ul>');
        return processedLines.join('<br>').replace(/<\/ul><br><ul>/g, '').replace(/<\/li><br><li>/g, '</li><li>');
    }

    /* ==========================================================================
       Message Dispatch (Send Query & Lock Controls)
       ========================================================================== */
    function submitMessage() {
        const text = chatInput.value.trim();
        if (!text) return;
        
        chatInput.value = '';
        adjustTextareaHeight();
        validateInput();
        hideAutocomplete();
        
        if (!activeChatId) {
            // Auto-create chat first
            fetch('/api/chats', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                }
            })
            .then(res => res.json())
            .then(chat => {
                activeChatId = chat.id;
                activeChatTitle.textContent = chat.title;
                fetchChats(false);
                postMessageRequest(chat.id, text);
            })
            .catch(err => console.error("Error creating session pre-post:", err));
        } else {
            postMessageRequest(activeChatId, text);
        }
    }

    function postMessageRequest(chatId, text) {
        appendMessageBubble({ role: 'user', content: text });
        scrollToBottom();
        
        appendTypingIndicator();
        
        // LOCK CONTROLS while API request is in flight
        chatInput.disabled = true;
        sendBtn.disabled = true;
        micBtn.disabled = true;
        
        fetch(`/api/chats/${chatId}/messages`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({ content: text })
        })
        .then(res => res.json())
        .then(data => {
            // UNLOCK CONTROLS
            chatInput.disabled = false;
            micBtn.disabled = false;
            
            removeTypingIndicator();
            
            appendMessageBubble(data.assistant_message);
            scrollToBottom();
            
            fetchChats(false);
            
            // Auto inspect the user query for immediate feedback
            inspectMessage(data.user_message);
            
            chatInput.focus();
        })
        .catch(err => {
            // UNLOCK CONTROLS on error
            chatInput.disabled = false;
            micBtn.disabled = false;
            
            removeTypingIndicator();
            console.error("API transmission error:", err);
            
            appendMessageBubble({
                role: 'bot',
                content: JSON.stringify({
                    type: "error",
                    title: "Connection Error",
                    confidence: 0.0,
                    explanation: "API endpoint is unreachable.",
                    data: { error_message: "An unexpected error occurred while communicating with the Flask backend. Please verify the server is running." }
                })
            });
            scrollToBottom();
            validateInput();
        });
    }

    /* ==========================================================================
       NLP Inspector Panel Renderer (Pipeline Flowchart)
       ========================================================================== */
    function resetInspector() {
        selectedNlpData = null;
        if (inspectorBanner) inspectorBanner.style.display = 'flex';
        if (inspectorContent) inspectorContent.style.display = 'none';
        if (inspectorSourceText) inspectorSourceText.textContent = '';
        if (inspectorLatencyText) inspectorLatencyText.textContent = '0 ms';
    }

    function inspectMessage(msg) {
        selectedNlpData = msg.nlp_analysis;
        
        if (!selectedNlpData) {
            inspectorBanner.style.display = 'flex';
            inspectorContent.style.display = 'none';
            return;
        }
        
        inspectorBanner.style.display = 'none';
        inspectorContent.style.display = 'block';
        toggleRightInspector(false);
        
        const origText = selectedNlpData.original_text || msg.content || '';
        inspectorSourceText.textContent = origText;
        
        // Update latency pill & Hero Stats
        if (inspectorLatencyText) {
            inspectorLatencyText.textContent = `${selectedNlpData.processing_time || 0} ms`;
        }
        
        const rawTokens = selectedNlpData.tokens || [];
        const cleanTokens = selectedNlpData.filtered_tokens || selectedNlpData.cleaned_tokens || [];
        const stemmedTokens = selectedNlpData.stemmed_tokens || [];
        const entities = selectedNlpData.entities || [];
        
        if (statTokenCount) {
            statTokenCount.innerHTML = `<i class="fa-solid fa-font"></i> ${rawTokens.length} tokens`;
        }
        if (statIntentBadge) {
            const intentName = (selectedNlpData.intent_detected || 'GENERAL').toUpperCase();
            statIntentBadge.textContent = `INTENT: ${intentName}`;
        }
        
        // Update dynamic tab count badges
        if (badgeTokensCount) badgeTokensCount.textContent = rawTokens.length;
        if (badgeNerCount) badgeNerCount.textContent = entities.length;
        
        // 1. Render Interactive Pipeline Stepper
        renderPipelineFlowchart(selectedNlpData);
        
        // 2. Render Tokens Analytics Tab
        renderTokensTab(selectedNlpData);
        
        // 3. Render Syntax & POS Tab
        renderPosTags(selectedNlpData.pos_tags);
        
        chunkTreeVisual.innerHTML = '';
        if (selectedNlpData.chunks) {
            const chunkObj = typeof selectedNlpData.chunks === 'string' 
                ? JSON.parse(selectedNlpData.chunks) 
                : selectedNlpData.chunks;
            renderChunkTree(chunkObj, chunkTreeVisual);
        } else {
            chunkTreeVisual.innerHTML = `<span class="text-muted" style="font-size:0.8rem;">No syntactic phrase chunk tree computed.</span>`;
        }
        
        // 4. Render NER Section with in-text highlighting
        renderNerSection(selectedNlpData);
        
        // 5. Render Topics (LDA) Tab
        const lda = selectedNlpData.topics_lda || selectedNlpData.topics;
        if (lda && lda.topics && lda.topics.length > 0) {
            noLdaMessage.style.display = 'none';
            ldaHasData.style.display = 'block';
            renderLdaTopics(lda);
        } else {
            ldaHasData.style.display = 'none';
            noLdaMessage.style.display = 'block';
            if (lda && lda.error) {
                noLdaMessage.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> <strong>LDA Info:</strong><br>${lda.error}`;
            } else {
                noLdaMessage.innerHTML = `<i class="fa-solid fa-circle-info"></i> Topic modeling was not executed for this sentence. LDA requires larger texts containing approximately 80+ words.`;
            }
        }
        
        switchTab('tab-overview');
    }

    function renderPipelineFlowchart(nlpData) {
        pipelineFlowchart.innerHTML = '';
        
        const conf = nlpData.intent_confidence !== undefined ? nlpData.intent_confidence : 1.0;
        let confLevel = 'high';
        let confText = 'High';
        if (conf < 0.60) {
            confLevel = 'low';
            confText = 'Low';
        } else if (conf < 0.90) {
            confLevel = 'medium';
            confText = 'Medium';
        }
        const confPct = Math.round(conf * 100);
        
        const rawTokens = nlpData.tokens || [];
        const cleanTokens = nlpData.filtered_tokens || nlpData.cleaned_tokens || [];
        const stopWords = nlpData.removed_stop_words || [];
        const sentiment = nlpData.sentiment;
        
        // Stage 1: Ingestion
        const stage1 = createStepperStage(
            'fa-solid fa-arrow-down-to-bracket',
            'Stage 1: Input Ingestion & Lexical Extraction',
            `${rawTokens.length} Tokens`,
            `<div style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px;">
                ${rawTokens.map(t => `<span class="token-badge">${escapeHtml(t)}</span>`).join('')}
             </div>`
        );
        pipelineFlowchart.appendChild(stage1);
        
        // Stage 2: Intent Classification & Routing
        const stage2 = createStepperStage(
            'fa-solid fa-route',
            'Stage 2: Intent Classification & Routing',
            nlpData.selected_module || 'nlp.general',
            `<div>
                <div style="display: flex; align-items: center; justify-content: space-between; font-size: 0.8rem;">
                    <span>Intent: <strong>${(nlpData.intent_detected || 'general').toUpperCase()}</strong></span>
                    <span class="confidence-indicator ${confLevel}">${confText} (${confPct}%)</span>
                </div>
                <div class="confidence-meter-wrapper">
                    <div class="confidence-bar-bg">
                        <div class="confidence-bar-fill ${confLevel}" style="width: ${confPct}%;"></div>
                    </div>
                </div>
             </div>`
        );
        pipelineFlowchart.appendChild(stage2);
        
        // Stage 3: Preprocessing & Information Extraction
        const stage3 = createStepperStage(
            'fa-solid fa-filter',
            'Stage 3: Information Word Filtering',
            `${cleanTokens.length} Information Words`,
            `<div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 6px;">
                Removed <strong>${stopWords.length}</strong> stop-words (${stopWords.slice(0, 5).join(', ')}${stopWords.length > 5 ? '...' : ''})
             </div>
             <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                ${cleanTokens.map(t => `<span class="token-badge" style="border-color: rgba(180, 190, 254, 0.3); color: var(--accent);">${escapeHtml(t)}</span>`).join('')}
             </div>`
        );
        pipelineFlowchart.appendChild(stage3);
        
        // Stage 4: Sentiment Intelligence (if available)
        if (sentiment) {
            const compound = sentiment.compound !== undefined ? sentiment.compound : 0;
            const pos = Math.round((sentiment.pos || 0) * 100);
            const neu = Math.round((sentiment.neu || 1) * 100);
            const neg = Math.round((sentiment.neg || 0) * 100);
            const label = (sentiment.label || 'neutral').toLowerCase();
            
            const stage4 = createStepperStage(
                'fa-solid fa-heart-pulse',
                'Stage 4: Sentiment & Polarity Analysis',
                sentiment.label ? sentiment.label.toUpperCase() : 'NEUTRAL',
                `<div class="sentiment-card-inner">
                    <div class="sentiment-bar-track">
                        <div class="sentiment-seg-pos" style="width: ${pos}%;" title="Positive: ${pos}%"></div>
                        <div class="sentiment-seg-neu" style="width: ${neu}%;" title="Neutral: ${neu}%"></div>
                        <div class="sentiment-seg-neg" style="width: ${neg}%;" title="Negative: ${neg}%"></div>
                    </div>
                    <div class="sentiment-metrics-row">
                        <span class="sentiment-metric-tag"><span class="legend-dot pos"></span> Pos: ${pos}%</span>
                        <span class="sentiment-metric-tag"><span class="legend-dot neu"></span> Neu: ${neu}%</span>
                        <span class="sentiment-metric-tag"><span class="legend-dot neg"></span> Neg: ${neg}%</span>
                        <span style="font-weight: 600; color: var(--text-main);">Compound: ${compound.toFixed(2)}</span>
                    </div>
                 </div>`
            );
            pipelineFlowchart.appendChild(stage4);
        }
        
        // Stage 5: Response Contract & Payload
        const responseJson = typeof nlpData.final_response === 'string' 
            ? nlpData.final_response 
            : JSON.stringify(nlpData.final_response, null, 2);
            
        const stage5 = createStepperStage(
            'fa-solid fa-file-code',
            'Stage 5: Final Response Payload',
            `${nlpData.processing_time || 0} ms`,
            `<div class="json-contract-viewer">${escapeHtml(responseJson)}</div>`,
            true
        );
        pipelineFlowchart.appendChild(stage5);
    }
    
    function createStepperStage(iconClass, title, badgeText, contentHtml, isLast = false) {
        const stage = document.createElement('div');
        stage.className = 'stepper-stage';
        
        let lineHtml = isLast ? '' : '<div class="stepper-line"></div>';
        
        stage.innerHTML = `
            ${lineHtml}
            <div class="stepper-icon"><i class="${iconClass}"></i></div>
            <div class="stepper-card">
                <div class="stepper-card-header">
                    <span class="stepper-title">${title}</span>
                    <span class="stepper-badge">${badgeText}</span>
                </div>
                <div class="stepper-content">${contentHtml}</div>
            </div>
        `;
        return stage;
    }

    function renderTokensTab(nlpData) {
        const raw = nlpData.tokens || [];
        const clean = nlpData.filtered_tokens || nlpData.cleaned_tokens || [];
        const stemmed = nlpData.stemmed_tokens || [];
        const stopWords = nlpData.removed_stop_words || [];
        
        // Unique tokens calculation
        const uniqueCount = new Set(raw.map(t => t.toLowerCase())).size;
        const diversityPct = raw.length > 0 ? Math.round((uniqueCount / raw.length) * 100) : 0;
        
        if (tokenStatsBar) {
            tokenStatsBar.innerHTML = `
                <div class="token-stat-item">
                    <div class="token-stat-num">${raw.length}</div>
                    <div class="token-stat-label">Total Tokens</div>
                </div>
                <div class="token-stat-item">
                    <div class="token-stat-num" style="color: #a6e3a1;">${clean.length}</div>
                    <div class="token-stat-label">Informative</div>
                </div>
                <div class="token-stat-item">
                    <div class="token-stat-num" style="color: #f38ba8;">${stopWords.length}</div>
                    <div class="token-stat-label">Stopwords</div>
                </div>
                <div class="token-stat-item">
                    <div class="token-stat-num" style="color: #89b4fa;">${diversityPct}%</div>
                    <div class="token-stat-label">Diversity</div>
                </div>
            `;
        }
        
        if (countRawTokens) countRawTokens.textContent = raw.length;
        if (countCleanTokens) countCleanTokens.textContent = clean.length;
        if (countStemmedTokens) countStemmedTokens.textContent = stemmed.length;
        
        renderTokenBadges(raw, tokensListRaw);
        renderTokenBadges(clean, tokensListClean);
        renderTokenBadges(stemmed, tokensListStemmed);
    }

    function renderTokenBadges(tokens, container) {
        container.innerHTML = '';
        if (!tokens || tokens.length === 0) {
            container.innerHTML = '<span class="text-muted" style="font-size:0.8rem;">[None]</span>';
            return;
        }
        tokens.forEach(tok => {
            const badge = document.createElement('span');
            badge.className = 'token-badge';
            badge.textContent = tok;
            container.appendChild(badge);
        });
    }

    function renderPosTags(tags) {
        posTagsList.innerHTML = '';
        if (!tags || tags.length === 0) {
            posTagsList.innerHTML = '<span class="text-muted" style="font-size:0.8rem;">[No POS tags generated]</span>';
            return;
        }
        tags.forEach(pair => {
            const word = pair[0];
            const tag = pair[1];
            const categoryClass = getPosCategoryClass(tag);
            const meaning = getPosMeaning(tag);
            
            const bubble = document.createElement('div');
            bubble.className = `pos-tag-bubble ${categoryClass}`;
            bubble.title = `${word}: ${meaning} (${tag})`;
            bubble.innerHTML = `
                <span class="pos-word">${escapeHtml(word)}</span>
                <span class="pos-tag-label">${tag}</span>
            `;
            posTagsList.appendChild(bubble);
        });
    }

    function getPosCategoryClass(tag) {
        if (!tag) return 'pos-other';
        const t = tag.toUpperCase();
        if (t.startsWith('NN')) return 'pos-noun';
        if (t.startsWith('VB') || t === 'MD') return 'pos-verb';
        if (t.startsWith('JJ')) return 'pos-adj';
        if (t.startsWith('RB') || t.startsWith('WRB')) return 'pos-adv';
        if (t.startsWith('PRP') || t.startsWith('WP')) return 'pos-pron';
        return 'pos-other';
    }

    function getPosMeaning(tag) {
        const mappings = {
            'CC': 'Coordinating conjunction', 'CD': 'Cardinal number', 'DT': 'Determiner',
            'EX': 'Existential there', 'FW': 'Foreign word', 'IN': 'Preposition / Conjunction',
            'JJ': 'Adjective', 'JJR': 'Adjective, comparative', 'JJS': 'Adjective, superlative',
            'MD': 'Modal auxiliary', 'NN': 'Noun, singular', 'NNS': 'Noun, plural',
            'NNP': 'Proper noun, singular', 'NNPS': 'Proper noun, plural', 'PDT': 'Predeterminer',
            'POS': 'Possessive ending', 'PRP': 'Personal pronoun', 'PRP$': 'Possessive pronoun',
            'RB': 'Adverb', 'RBR': 'Adverb, comparative', 'RBS': 'Adverb, superlative',
            'RP': 'Particle', 'TO': 'to', 'UH': 'Interjection', 'VB': 'Verb, base form',
            'VBD': 'Verb, past tense', 'VBG': 'Verb, gerund/participle', 'VBN': 'Verb, past participle',
            'VBP': 'Verb, non-3rd person sing. present', 'VBZ': 'Verb, 3rd person sing. present', 'WDT': 'Wh-determiner',
            'WP': 'Wh-pronoun', 'WP$': 'Possessive wh-pronoun', 'WRB': 'Wh-adverb'
        };
        return mappings[tag] || 'Part of Speech';
    }

    function renderChunkTree(node, container) {
        if (!node) return;
        
        if (node.children !== undefined) {
            const nodeDiv = document.createElement('div');
            nodeDiv.className = 'tree-node';
            
            const label = document.createElement('span');
            label.className = 'node-label';
            label.textContent = node.label;
            nodeDiv.appendChild(label);
            
            node.children.forEach(child => {
                renderChunkTree(child, nodeDiv);
            });
            
            container.appendChild(nodeDiv);
        } else {
            const leafDiv = document.createElement('div');
            leafDiv.className = 'node-leaf';
            
            const wordSpan = document.createElement('span');
            wordSpan.className = 'node-leaf-word';
            wordSpan.textContent = node.word;
            
            const tagSpan = document.createElement('span');
            tagSpan.className = 'node-leaf-tag';
            tagSpan.textContent = `(${node.tag})`;
            
            leafDiv.appendChild(wordSpan);
            leafDiv.appendChild(tagSpan);
            container.appendChild(leafDiv);
        }
    }

    function renderNerSection(nlpData) {
        const entities = nlpData.entities || [];
        const originalText = nlpData.original_text || '';
        
        // 1. In-text entity highlighter
        if (nerHighlightedBox) {
            if (!entities || entities.length === 0) {
                nerHighlightedBox.innerHTML = `<em>${escapeHtml(originalText)}</em>`;
            } else {
                let markedText = escapeHtml(originalText);
                entities.forEach(ent => {
                    const escapedEntText = escapeHtml(ent.text);
                    const labelLower = (ent.label || 'other').toLowerCase();
                    let colorClass = ['person', 'org', 'gpe', 'date', 'time', 'money', 'percent', 'cardinal', 'ordinal', 'location'].includes(labelLower)
                        ? (labelLower === 'location' ? 'gpe' : labelLower)
                        : 'other';
                    
                    const spanTag = `<span class="ner-highlight-span ${colorClass}" title="${ent.label}">${escapedEntText}</span>`;
                    markedText = markedText.replace(escapedEntText, spanTag);
                });
                nerHighlightedBox.innerHTML = markedText;
            }
        }
        
        // 2. Entities Table
        nerTableBody.innerHTML = '';
        if (!entities || entities.length === 0) {
            noNerMessage.style.display = 'block';
            return;
        }
        noNerMessage.style.display = 'none';
        
        entities.forEach(ent => {
            const tr = document.createElement('tr');
            const labelLower = (ent.label || 'other').toLowerCase();
            let colorClass = ['person', 'org', 'gpe', 'date', 'time', 'money', 'percent', 'cardinal', 'ordinal', 'location'].includes(labelLower)
                ? (labelLower === 'location' ? 'gpe' : labelLower)
                : 'other';
            
            let iconClass = 'fa-tag';
            if (labelLower === 'person') iconClass = 'fa-user';
            else if (labelLower === 'org') iconClass = 'fa-building';
            else if (labelLower === 'gpe' || labelLower === 'location') iconClass = 'fa-earth-americas';
            else if (labelLower === 'date' || labelLower === 'time') iconClass = 'fa-calendar';
            else if (labelLower === 'money' || labelLower === 'percent') iconClass = 'fa-coins';
            else if (labelLower === 'cardinal' || labelLower === 'ordinal') iconClass = 'fa-arrow-down-1-9';
            
            tr.innerHTML = `
                <td><strong>${escapeHtml(ent.text)}</strong></td>
                <td><span style="font-size: 0.78rem; text-transform: capitalize; color: var(--text-muted);">${labelLower}</span></td>
                <td><span class="ner-label-badge ${colorClass}"><i class="fa-solid ${iconClass}"></i> ${ent.label}</span></td>
            `;
            nerTableBody.appendChild(tr);
        });
    }

    function renderLdaTopics(lda) {
        ldaTopicsList.innerHTML = '';
        ldaSentencesList.innerHTML = '';
        
        lda.topics.forEach(t => {
            const card = document.createElement('div');
            card.className = 'topic-card';
            
            const header = document.createElement('div');
            header.className = 'topic-header';
            header.innerHTML = `<span><i class="fa-solid fa-shapes"></i> Topic #${t.topic_id}</span>`;
            
            const wordsDiv = document.createElement('div');
            wordsDiv.className = 'topic-words';
            
            t.words.forEach(word => {
                const badge = document.createElement('span');
                badge.className = 'topic-word-badge';
                badge.textContent = word;
                wordsDiv.appendChild(badge);
            });
            
            card.appendChild(header);
            card.appendChild(wordsDiv);
            ldaTopicsList.appendChild(card);
        });
        
        if (lda.document_distribution) {
            lda.document_distribution.forEach(doc => {
                const item = document.createElement('div');
                item.className = 'lda-doc-item';
                
                const textDiv = document.createElement('div');
                textDiv.className = 'lda-doc-text';
                textDiv.textContent = `"${doc.text}"`;
                
                const proportionsDiv = document.createElement('div');
                proportionsDiv.className = 'lda-doc-proportions';
                
                const props = doc.topics.map((val, idx) => {
                    return `Topic ${idx + 1}: <strong>${Math.round(val * 100)}%</strong>`;
                });
                proportionsDiv.innerHTML = props.join(' | ');
                
                item.appendChild(textDiv);
                item.appendChild(proportionsDiv);
                ldaSentencesList.appendChild(item);
            });
        }
    }

    /* ==========================================================================
       Autocomplete - Google Keyboard (Gboard) Style Instant Horizontal Strip
       ========================================================================== */
    const AUTOCOMPLETE_VOCAB = [
        "summarize", "summary", "translate", "translation", "sentiment", "ner", "entities", 
        "pos", "parts-of-speech", "chunk", "chunking", "topic", "lda", "wikipedia", "search",
        "math", "calculate", "solve", "algebra", "equation", "formula", "grammar", "syntax",
        "hello", "hi", "hey", "how", "what", "where", "who", "why", "when", "which", "whose",
        "help", "explain", "analyze", "generate", "information", "about", "describe", "define",
        "python", "javascript", "flask", "sqlite", "nlp", "chatbot", "natural", "language", "processing", 
        "artificial", "intelligence", "machine", "learning", "data", "science", "software", 
        "development", "computer", "system", "programming", "developer", "browser", "interface",
        "algorithm", "neural", "network", "transformer", "spacy", "nltk", "scikit-learn",
        "analysis", "analytics", "performance", "database", "security", "function", "variable",
        "response", "question", "message", "conversation", "context", "history", "settings",
        "overview", "tokens", "tokenization", "stemming", "lemmatization", "classification"
    ];

    let currentLookupWord = "";

    function getInstantSuggestions(typedWord) {
        if (!typedWord || typedWord.length < 1) return [];
        const prefix = typedWord.toLowerCase().trim();
        const results = new Set();
        
        // 1. Built-in vocabulary match
        for (const w of AUTOCOMPLETE_VOCAB) {
            const wl = w.toLowerCase();
            if (wl.startsWith(prefix) && wl !== prefix) {
                results.add(wl);
            }
        }
        
        // 2. Client-side harvested conversation words (instant 0ms memory cache)
        const messagesEl = document.getElementById('chat-messages');
        if (messagesEl) {
            const textContent = messagesEl.innerText || '';
            const matches = textContent.match(/\b[a-zA-Z]{2,20}\b/g) || [];
            for (const w of matches) {
                const wl = w.toLowerCase();
                if (wl.startsWith(prefix) && wl !== prefix) {
                    results.add(wl);
                }
            }
        }
        
        const commands = ["summarize", "translate", "sentiment", "ner", "pos", "chunk", "topic", "math", "wikipedia"];
        return Array.from(results).sort((a, b) => {
            const aIsCmd = commands.includes(a);
            const bIsCmd = commands.includes(b);
            if (aIsCmd && !bIsCmd) return -1;
            if (!aIsCmd && bIsCmd) return 1;
            if (a.length !== b.length) return a.length - b.length;
            return a.localeCompare(b);
        }).slice(0, 10);
    }

    function handleInput() {
        adjustTextareaHeight();
        validateInput();
        
        const text = chatInput.value;
        const cursorPos = chatInput.selectionStart;
        
        const textBeforeCursor = text.slice(0, cursorPos);
        const words = textBeforeCursor.split(/[\s,;:]+/);
        const currentWord = words[words.length - 1];
        
        clearTimeout(debounceTimer);
        currentLookupWord = currentWord;
        
        if (!currentWord || currentWord.length < 1) {
            hideAutocomplete();
            return;
        }
        
        // 1. Instant 0ms local match based on active user typing
        const instantMatches = getInstantSuggestions(currentWord);
        if (instantMatches.length > 0) {
            autocompleteSuggestions = instantMatches;
            renderAutocompletePopup(currentWord);
        } else {
            hideAutocomplete();
        }
        
        // 2. Ultra-fast background fetch for any additional backend vocabulary
        debounceTimer = setTimeout(() => {
            fetchAutocomplete(currentWord);
        }, 20);
    }

    function fetchAutocomplete(word) {
        if (!word) return;
        const url = `/api/autocomplete?q=${encodeURIComponent(word)}&chat_id=${activeChatId || ''}`;
        fetch(url)
            .then(res => res.json())
            .then(suggestions => {
                if (currentLookupWord !== word) return; // Discard stale responses
                
                if (suggestions && suggestions.length > 0) {
                    const combined = Array.from(new Set([...autocompleteSuggestions, ...suggestions]));
                    const prefix = word.toLowerCase();
                    const filtered = combined.filter(w => w.toLowerCase().startsWith(prefix) && w.toLowerCase() !== prefix);
                    if (filtered.length > 0) {
                        autocompleteSuggestions = filtered.slice(0, 10);
                        renderAutocompletePopup(word);
                    }
                }
            })
            .catch(err => console.error("Autocomplete lookup error:", err));
    }

    function renderAutocompletePopup(typedWord) {
        autocompletePopup.innerHTML = '';
        autocompleteSelectedIdx = -1;
        
        if (!autocompleteSuggestions || autocompleteSuggestions.length === 0) {
            hideAutocomplete();
            return;
        }
        
        autocompleteSuggestions.forEach((sugg, idx) => {
            const item = document.createElement('div');
            item.className = 'autocomplete-item';
            item.setAttribute('data-index', idx);
            item.textContent = sugg;
            
            item.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                selectAutocompleteSuggestion(sugg, typedWord);
            });
            
            autocompletePopup.appendChild(item);
        });
        
        autocompletePopup.style.display = 'flex';
    }

    function selectAutocompleteSuggestion(word, typedWord) {
        const text = chatInput.value;
        const cursorPos = chatInput.selectionStart;
        const textBeforeCursor = text.slice(0, cursorPos);
        const textAfterCursor = text.slice(cursorPos);
        
        const lastWordIndex = textBeforeCursor.lastIndexOf(typedWord);
        const completion = word + " ";
        
        const newTextBefore = textBeforeCursor.slice(0, lastWordIndex) + completion;
        
        chatInput.value = newTextBefore + textAfterCursor;
        chatInput.focus();
        
        const newCursorPos = newTextBefore.length;
        chatInput.setSelectionRange(newCursorPos, newCursorPos);
        
        hideAutocomplete();
        adjustTextareaHeight();
        validateInput();
    }

    function hideAutocomplete() {
        autocompletePopup.style.display = 'none';
        autocompletePopup.innerHTML = '';
        autocompleteSuggestions = [];
        autocompleteSelectedIdx = -1;
    }

    /* ==========================================================================
       Keyboard Navigation
       ========================================================================== */
    function handleKeyDown(e) {
        const key = e.key;
        
        if (autocompletePopup.style.display === 'flex' || autocompletePopup.style.display === 'block') {
            const items = autocompletePopup.querySelectorAll('.autocomplete-item');
            
            if (key === 'ArrowRight' || key === 'ArrowDown') {
                e.preventDefault();
                autocompleteSelectedIdx = (autocompleteSelectedIdx + 1) % items.length;
                updateAutocompleteSelection(items);
            } 
            else if (key === 'ArrowLeft' || key === 'ArrowUp') {
                e.preventDefault();
                autocompleteSelectedIdx = (autocompleteSelectedIdx - 1 + items.length) % items.length;
                updateAutocompleteSelection(items);
            } 
            else if (key === 'Enter' || key === 'Tab') {
                e.preventDefault();
                if (autocompleteSelectedIdx >= 0 && autocompleteSelectedIdx < items.length) {
                    const selectedWord = autocompleteSuggestions[autocompleteSelectedIdx];
                    const text = chatInput.value;
                    const cursorPos = chatInput.selectionStart;
                    const textBeforeCursor = text.slice(0, cursorPos);
                    const words = textBeforeCursor.split(/[\s,;:]+/);
                    const typedWord = words[words.length - 1];
                    
                    selectAutocompleteSuggestion(selectedWord, typedWord);
                } else if (items.length > 0) {
                    const selectedWord = autocompleteSuggestions[0];
                    const text = chatInput.value;
                    const cursorPos = chatInput.selectionStart;
                    const textBeforeCursor = text.slice(0, cursorPos);
                    const words = textBeforeCursor.split(/[\s,;:]+/);
                    const typedWord = words[words.length - 1];
                    
                    selectAutocompleteSuggestion(selectedWord, typedWord);
                }
            } 
            else if (key === 'Escape') {
                e.preventDefault();
                hideAutocomplete();
            }
            return;
        }
        
        if (key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            submitMessage();
        }
    }

    function updateAutocompleteSelection(items) {
        items.forEach((item, idx) => {
            if (idx === autocompleteSelectedIdx) {
                item.classList.add('selected');
                item.scrollIntoView({ block: 'nearest' });
            } else {
                item.classList.remove('selected');
            }
        });
    }

    /* ==========================================================================
       Helpers & Custom Confirm
       ========================================================================== */
    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function adjustTextareaHeight() {
        chatInput.style.height = 'auto';
        
        const text = chatInput.value;
        const explicitLines = (text.match(/\n/g) || []).length + 1;
        const computedLines = Math.max(
            explicitLines,
            Math.floor((chatInput.scrollHeight - 16) / 22)
        );
        
        if (expandToggleBtn) {
            if (computedLines > 3) {
                expandToggleBtn.style.display = 'flex';
                chatInput.classList.add('has-expand-btn');
            } else {
                expandToggleBtn.style.display = 'none';
                chatInput.classList.remove('has-expand-btn');
                isExpanded = false;
                expandToggleBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-maximize-2"><polyline points="15 3 21 3 21 9"></polyline><polyline points="9 21 3 21 3 15"></polyline><line x1="21" y1="3" x2="14" y2="10"></line><line x1="3" y1="21" x2="10" y2="14"></line></svg>`;
                expandToggleBtn.title = "Expand input";
            }
        }
        
        const maxHeight = isExpanded ? 360 : 130;
        chatInput.style.height = Math.min(chatInput.scrollHeight, maxHeight) + 'px';
        updateScrollClearance();
    }

    function updateScrollClearance() {
        const wrapper = document.querySelector('.input-wrapper');
        const clearanceDiv = document.getElementById('chat-scroll-clearance');
        if (wrapper) {
            const height = wrapper.offsetHeight + 28;
            if (clearanceDiv) {
                clearanceDiv.style.height = height + 'px';
            }
        }
    }

    function validateInput() {
        const text = chatInput.value.trim();
        sendBtn.disabled = (text === '');
    }

    function showCustomConfirm(title, message, onConfirm) {
        const modal = document.getElementById('confirm-modal');
        if (!modal) return;
        const titleEl = modal.querySelector('h3');
        const bodyEl = modal.querySelector('.modal-body p');
        const okBtn = document.getElementById('confirm-ok-btn');
        const cancelBtn = document.getElementById('confirm-cancel-btn');
        
        if (titleEl) titleEl.textContent = title;
        if (bodyEl) bodyEl.textContent = message;
        
        // Cleanly clone buttons to eliminate stale listeners
        const newOkBtn = okBtn.cloneNode(true);
        const newCancelBtn = cancelBtn.cloneNode(true);
        okBtn.parentNode.replaceChild(newOkBtn, okBtn);
        cancelBtn.parentNode.replaceChild(newCancelBtn, cancelBtn);
        
        modal.classList.add('visible');
        
        const closeModal = () => {
            modal.classList.remove('visible');
        };
        
        newOkBtn.addEventListener('click', (e) => {
            e.preventDefault();
            closeModal();
            if (typeof onConfirm === 'function') {
                onConfirm();
            }
        });
        
        newCancelBtn.addEventListener('click', (e) => {
            e.preventDefault();
            closeModal();
        });
        
        const onOverlayClick = (e) => {
            if (e.target === modal) {
                closeModal();
                modal.removeEventListener('click', onOverlayClick);
            }
        };
        modal.addEventListener('click', onOverlayClick);
    }

    /* ==========================================================================
       Appearance & Theme Management
       ========================================================================== */
    function applyTheme(theme) {
        const targetTheme = theme === 'light' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', targetTheme);
        document.body.setAttribute('data-theme', targetTheme);
        localStorage.setItem('x_pilot_theme', targetTheme);
        
        const darkBtn = document.getElementById('theme-btn-dark');
        const lightBtn = document.getElementById('theme-btn-light');
        if (darkBtn && lightBtn) {
            if (targetTheme === 'light') {
                lightBtn.classList.add('active');
                darkBtn.classList.remove('active');
            } else {
                darkBtn.classList.add('active');
                lightBtn.classList.remove('active');
            }
        }
    }

    function applyFontSize(size) {
        const targetSize = ['small', 'medium', 'large'].includes(size) ? size : 'medium';
        document.documentElement.setAttribute('data-font-size', targetSize);
        document.body.setAttribute('data-font-size', targetSize);
        localStorage.setItem('x_pilot_font_size', targetSize);
        
        const fontSizeSelect = document.getElementById('settings-font-size-select');
        if (fontSizeSelect) {
            fontSizeSelect.value = targetSize;
        }
    }

    function loadSavedAppearance() {
        const savedTheme = localStorage.getItem('x_pilot_theme') || 'dark';
        applyTheme(savedTheme);

        const savedFontSize = localStorage.getItem('x_pilot_font_size') || 'medium';
        applyFontSize(savedFontSize);
    }

    /* ==========================================================================
       Settings Modal Interaction & Full Options Handling
       ========================================================================== */
    const settingsBtn = document.getElementById('settings-btn');
    const settingsModal = document.getElementById('settings-modal');
    const settingsCloseBtn = document.getElementById('settings-close-btn');
    const settingsSaveBtn = document.getElementById('settings-save-btn');
    const settingsApiKeyInput = document.getElementById('settings-api-key');
    const settingsUsernameDisplay = document.getElementById('settings-username-display');

    if (settingsBtn) {
        settingsBtn.addEventListener('click', () => {
            fetch('/api/settings')
                .then(res => res.json())
                .then(data => {
                    if (settingsUsernameDisplay) settingsUsernameDisplay.textContent = data.username;
                    if (settingsApiKeyInput) settingsApiKeyInput.value = data.gemini_api_key;
                    settingsModal.classList.add('visible');
                })
                .catch(err => console.error("Error loading account settings:", err));
        });
    }

    if (settingsCloseBtn) {
        settingsCloseBtn.addEventListener('click', () => {
            settingsModal.classList.remove('visible');
        });
    }

    if (settingsSaveBtn) {
        settingsSaveBtn.addEventListener('click', () => {
            const apiKey = settingsApiKeyInput.value.trim();
            fetch('/api/settings', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({ gemini_api_key: apiKey })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showCustomConfirm("Settings Saved", "Your API key and account settings have been updated.", () => {});
                    settingsModal.classList.remove('visible');
                } else {
                    showCustomConfirm("Save Failed", data.message || "Could not save settings.", () => {});
                }
            })
            .catch(err => {
                console.error("Error saving settings:", err);
                showCustomConfirm("Error", "An unexpected error occurred while saving settings.", () => {});
            });
        });
    }

    // 1. Model Hyperparameters (Temperature & Max Tokens)
    const tempRangeInput = document.getElementById('temp-range-input');
    const tempValDisplay = document.getElementById('temp-val-display');
    const maxTokensSelect = document.getElementById('max-tokens-select');
    
    if (tempRangeInput && tempValDisplay) {
        const savedTemp = localStorage.getItem('x_pilot_temperature') || '0.7';
        tempRangeInput.value = savedTemp;
        tempValDisplay.textContent = savedTemp;
        tempRangeInput.addEventListener('input', () => {
            tempValDisplay.textContent = tempRangeInput.value;
            localStorage.setItem('x_pilot_temperature', tempRangeInput.value);
        });
    }

    if (maxTokensSelect) {
        const savedTokens = localStorage.getItem('x_pilot_max_tokens') || '1000';
        maxTokensSelect.value = savedTokens;
        maxTokensSelect.addEventListener('change', () => {
            localStorage.setItem('x_pilot_max_tokens', maxTokensSelect.value);
        });
    }

    // 2. Clear All Conversations (Custom Modal Alert matching delete chat)
    const clearAllConversationsBtn = document.getElementById('clear-all-conversations-btn');
    if (clearAllConversationsBtn) {
        clearAllConversationsBtn.addEventListener('click', () => {
            showCustomConfirm(
                'Clear All Conversations',
                'Are you sure you want to delete all chat conversations? This will permanently wipe your entire chat history and cannot be undone.',
                () => {
                    fetch('/api/chats', {
                        method: 'DELETE',
                        headers: {
                            'X-CSRFToken': getCsrfToken()
                        }
                    })
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            chats = [];
                            activeChatId = null;
                            localStorage.removeItem('activeChatId');
                            renderChatList();
                            clearMessagesFeed();
                            showWelcome();
                            activeChatTitle.textContent = 'New Chat';
                            resetInspector();
                            if (settingsModal) settingsModal.classList.remove('visible');
                            createNewChat();
                        }
                    })
                    .catch(err => console.error("Error clearing all conversations:", err));
                }
            );
        });
    }

    // 3. NLP Inspector Pipeline Toggles
    function bindPipelineToggle(btnId, storageKey) {
        const btn = document.getElementById(btnId);
        if (!btn) return;
        const saved = localStorage.getItem(storageKey);
        const isEnabled = saved === null ? true : saved === 'true';
        setToggleVisual(btn, isEnabled);
        
        btn.addEventListener('click', () => {
            const currentActive = btn.classList.contains('active');
            setToggleVisual(btn, !currentActive);
            localStorage.setItem(storageKey, (!currentActive).toString());
        });
    }

    function setToggleVisual(btn, active) {
        if (active) {
            btn.classList.add('active');
            btn.textContent = 'Enabled';
        } else {
            btn.classList.remove('active');
            btn.textContent = 'Disabled';
        }
    }

    bindPipelineToggle('toggle-nlp-tokens', 'x_pilot_nlp_tokens');
    bindPipelineToggle('toggle-nlp-ner', 'x_pilot_nlp_ner');
    bindPipelineToggle('toggle-nlp-lda', 'x_pilot_nlp_lda');

    // 4. Appearance Controls (Theme & Font Size)
    const themeBtnDark = document.getElementById('theme-btn-dark');
    const themeBtnLight = document.getElementById('theme-btn-light');
    if (themeBtnDark) {
        themeBtnDark.addEventListener('click', () => applyTheme('dark'));
    }
    if (themeBtnLight) {
        themeBtnLight.addEventListener('click', () => applyTheme('light'));
    }

    const settingsFontSizeSelect = document.getElementById('settings-font-size-select');
    if (settingsFontSizeSelect) {
        settingsFontSizeSelect.addEventListener('change', () => applyFontSize(settingsFontSizeSelect.value));
    }

    if (settingsModal) {
        settingsModal.addEventListener('click', (e) => {
            if (e.target === settingsModal) {
                settingsModal.classList.remove('visible');
            }
        });

        // Tab selection switcher for redesigned settings menu items
        const menuItems = settingsModal.querySelectorAll('.settings-menu-item');
        const panes = settingsModal.querySelectorAll('.settings-pane-content');
        
        menuItems.forEach(item => {
            item.addEventListener('click', () => {
                const targetId = item.getAttribute('data-target');
                if (!targetId) return; // Ignore elements without data-target (like Logout button)
                
                // Toggle active menu item styling
                menuItems.forEach(m => m.classList.remove('active'));
                item.classList.add('active');
                
                // Show matching content pane, hide others
                panes.forEach(pane => {
                    if (pane.id === targetId) {
                        pane.style.display = 'block';
                    } else {
                        pane.style.display = 'none';
                    }
                });
            });
        });
    }

    // Launch Application
    init();
});
