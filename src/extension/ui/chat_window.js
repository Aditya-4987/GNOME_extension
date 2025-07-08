/**
 * Chat window component for AI Assistant Extension
 */

import GObject from 'gi://GObject';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as ModalDialog from 'resource:///org/gnome/shell/ui/modalDialog.js';

const ChatWindow = GObject.registerClass({
    Properties: {
        'visible': GObject.ParamSpec.boolean(
            'visible', 'visible', 'visible',
            GObject.ParamFlags.READWRITE,
            false
        ),
    },
    Signals: {
        'message-sent': {
            param_types: [GObject.TYPE_STRING]
        },
        'window-closed': {}
    },
}, class ChatWindow extends ModalDialog.ModalDialog {
    _init(serviceConnection) {
        super._init({ 
            styleClass: 'ai-assistant-chat-window',
            destroyOnClose: false
        });

        this._serviceConnection = serviceConnection;
        this._conversationHistory = [];
        this._isProcessing = false;

        this._buildUI();
        this._setupEventHandlers();
    }

    _buildUI() {
        // Main container
        this._container = new St.BoxLayout({
            vertical: true,
            style_class: 'ai-chat-container',
            width: 600,
            height: 500
        });

        // Header
        this._header = new St.BoxLayout({
            style_class: 'ai-chat-header',
            vertical: false
        });

        this._titleLabel = new St.Label({
            text: 'AI Assistant',
            style_class: 'ai-chat-title',
            x_expand: true
        });

        this._statusIcon = new St.Icon({
            icon_name: 'emblem-default-symbolic',
            style_class: 'ai-chat-status',
            icon_size: 16
        });

        this._minimizeButton = new St.Button({
            style_class: 'ai-chat-button',
            child: new St.Icon({
                icon_name: 'window-minimize-symbolic',
                icon_size: 16
            })
        });

        this._closeButton = new St.Button({
            style_class: 'ai-chat-button',
            child: new St.Icon({
                icon_name: 'window-close-symbolic',
                icon_size: 16
            })
        });

        this._header.add_child(this._titleLabel);
        this._header.add_child(this._statusIcon);
        this._header.add_child(this._minimizeButton);
        this._header.add_child(this._closeButton);

        // Chat area with scrolling
        this._chatScrollView = new St.ScrollView({
            style_class: 'ai-chat-scroll',
            hscrollbar_policy: St.PolicyType.NEVER,
            vscrollbar_policy: St.PolicyType.AUTOMATIC,
            y_expand: true
        });

        this._chatContent = new St.BoxLayout({
            vertical: true,
            style_class: 'ai-chat-content'
        });

        this._chatScrollView.add_actor(this._chatContent);

        // Input area
        this._inputArea = new St.BoxLayout({
            style_class: 'ai-chat-input-area',
            vertical: false
        });

        this._messageEntry = new St.Entry({
            style_class: 'ai-chat-entry',
            hint_text: 'Type your message...',
            x_expand: true,
            can_focus: true
        });

        this._sendButton = new St.Button({
            style_class: 'ai-chat-send-button',
            child: new St.Icon({
                icon_name: 'mail-send-symbolic',
                icon_size: 16
            }),
            reactive: true
        });

        this._voiceButton = new St.Button({
            style_class: 'ai-chat-voice-button',
            child: new St.Icon({
                icon_name: 'audio-input-microphone-symbolic',
                icon_size: 16
            }),
            reactive: true
        });

        this._inputArea.add_child(this._messageEntry);
        this._inputArea.add_child(this._voiceButton);
        this._inputArea.add_child(this._sendButton);

        // Status bar
        this._statusBar = new St.BoxLayout({
            style_class: 'ai-chat-status-bar',
            vertical: false
        });

        this._statusLabel = new St.Label({
            text: 'Ready',
            style_class: 'ai-chat-status-label',
            x_expand: true
        });

        this._typingIndicator = new St.Icon({
            icon_name: 'emblem-synchronizing-symbolic',
            style_class: 'ai-chat-typing',
            icon_size: 16,
            visible: false
        });

        this._statusBar.add_child(this._statusLabel);
        this._statusBar.add_child(this._typingIndicator);

        // Assemble the window
        this._container.add_child(this._header);
        this._container.add_child(this._chatScrollView);
        this._container.add_child(this._inputArea);
        this._container.add_child(this._statusBar);

        this.contentLayout.add_child(this._container);

        // Add welcome message
        this._addMessage('assistant', 'Hello! I\'m your AI assistant. How can I help you today?');
    }

    _setupEventHandlers() {
        // Send button
        this._sendButton.connect('clicked', () => {
            this._sendMessage();
        });

        // Enter key in message entry
        this._messageEntry.clutter_text.connect('activate', () => {
            this._sendMessage();
        });

        // Voice button
        this._voiceButton.connect('clicked', () => {
            this._toggleVoiceInput();
        });

        // Window controls
        this._minimizeButton.connect('clicked', () => {
            this.close();
        });

        this._closeButton.connect('clicked', () => {
            this.close();
            this.emit('window-closed');
        });

        // Service connection status
        if (this._serviceConnection) {
            this._serviceConnection.connect('status-changed', (connection, connected) => {
                this._updateConnectionStatus(connected);
            });
        }
    }

    _sendMessage() {
        const message = this._messageEntry.get_text().trim();
        if (!message || this._isProcessing) {
            return;
        }

        this._addMessage('user', message);
        this._messageEntry.set_text('');
        this._setProcessing(true);

        // Send to service
        this._sendToService(message);
    }

    async _sendToService(message) {
        try {
            if (!this._serviceConnection || !this._serviceConnection.connected) {
                throw new Error('Not connected to service');
            }

            this._setStatus('Thinking...');
            
            const response = await this._serviceConnection.sendRequest('/chat', {
                message: message,
                conversation_id: this._conversationId || null,
                context: this._getContext()
            });

            if (response.response) {
                this._addMessage('assistant', response.response);
                
                // Handle function calls if any
                if (response.function_calls && response.function_calls.length > 0) {
                    this._handleFunctionCalls(response.function_calls);
                }
                
                // Update context
                if (response.context) {
                    this._updateContext(response.context);
                }
                
                // Store conversation ID
                if (response.task_id) {
                    this._conversationId = response.task_id;
                }
            } else {
                throw new Error('Empty response from service');
            }

        } catch (error) {
            console.error('Error sending message:', error);
            this._addMessage('system', `Error: ${error.message}`, 'error');
        } finally {
            this._setProcessing(false);
            this._setStatus('Ready');
        }
    }

    _addMessage(sender, content, type = 'normal') {
        const messageBox = new St.BoxLayout({
            style_class: `ai-message ai-message-${sender} ai-message-${type}`,
            vertical: true,
            x_align: sender === 'user' ? Clutter.ActorAlign.END : Clutter.ActorAlign.START
        });

        // Sender label
        const senderLabel = new St.Label({
            text: sender.charAt(0).toUpperCase() + sender.slice(1),
            style_class: `ai-message-sender ai-message-sender-${sender}`
        });

        // Message content
        const contentLabel = new St.Label({
            text: content,
            style_class: `ai-message-content ai-message-content-${sender}`,
            x_align: Clutter.ActorAlign.START
        });
        contentLabel.clutter_text.set_line_wrap(true);
        contentLabel.clutter_text.set_line_wrap_mode(Clutter.WrapMode.WORD_CHAR);

        // Timestamp
        const timestamp = new St.Label({
            text: new Date().toLocaleTimeString(),
            style_class: 'ai-message-timestamp'
        });

        messageBox.add_child(senderLabel);
        messageBox.add_child(contentLabel);
        messageBox.add_child(timestamp);

        this._chatContent.add_child(messageBox);

        // Store in history
        this._conversationHistory.push({
            sender: sender,
            content: content,
            timestamp: Date.now()
        });

        // Scroll to bottom
        GLib.idle_add(GLib.PRIORITY_DEFAULT, () => {
            const adjustment = this._chatScrollView.vscroll.adjustment;
            adjustment.value = adjustment.upper - adjustment.page_size;
            return GLib.SOURCE_REMOVE;
        });
    }

    _handleFunctionCalls(functionCalls) {
        for (const call of functionCalls) {
            const toolName = call.name || 'Unknown Tool';
            const message = `🔧 Executing: ${toolName}`;
            this._addMessage('system', message, 'function-call');
        }
    }

    _setProcessing(processing) {
        this._isProcessing = processing;
        this._sendButton.reactive = !processing;
        this._messageEntry.reactive = !processing;
        this._typingIndicator.visible = processing;
        
        if (processing) {
            this._typingIndicator.add_style_class_name('spinning');
        } else {
            this._typingIndicator.remove_style_class_name('spinning');
        }
    }

    _setStatus(status) {
        this._statusLabel.set_text(status);
    }

    _updateConnectionStatus(connected) {
        if (connected) {
            this._statusIcon.set_icon_name('emblem-default-symbolic');
            this._statusIcon.remove_style_class_name('disconnected');
            this._setStatus('Connected');
        } else {
            this._statusIcon.set_icon_name('dialog-error-symbolic');
            this._statusIcon.add_style_class_name('disconnected');
            this._setStatus('Disconnected');
        }
    }

    _toggleVoiceInput() {
        // TODO: Implement voice input
        this._addMessage('system', 'Voice input not yet implemented', 'info');
    }

    _getContext() {
        return {
            conversation_history: this._conversationHistory.slice(-10), // Last 10 messages
            timestamp: Date.now(),
            window_state: 'chat'
        };
    }

    _updateContext(context) {
        // Update internal context if needed
        if (context.conversation_id) {
            this._conversationId = context.conversation_id;
        }
    }

    clearHistory() {
        this._conversationHistory = [];
        this._chatContent.destroy_all_children();
        this._addMessage('assistant', 'Hello! I\'m your AI assistant. How can I help you today?');
    }

    show() {
        super.open();
        this._messageEntry.grab_key_focus();
    }

    hide() {
        super.close();
    }

    destroy() {
        super.destroy();
    }
});
