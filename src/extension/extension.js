/**
 * GNOME AI Assistant Extension
 * 
 * Main extension file that provides UI integration with the AI assistant service
 */

import GObject from 'gi://GObject';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import {Extension, gettext as _} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import * as ModalDialog from 'resource:///org/gnome/shell/ui/modalDialog.js';

const SOCKET_PATH = '/tmp/gnome-ai-assistant.sock';

/**
 * Service connection manager
 */
class ServiceConnection {
    constructor() {
        this.connected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 2000; // 2 seconds
        this._connection = null;
        this._callbacks = new Map();
    }

    async connect() {
        try {
            // Check if socket exists
            const socketFile = Gio.File.new_for_path(SOCKET_PATH);
            if (!socketFile.query_exists(null)) {
                throw new Error('Service socket not found');
            }

            // For now, we'll use HTTP over Unix socket via curl as a fallback
            // Real implementation would use GSocketClient
            this.connected = true;
            this.reconnectAttempts = 0;
            console.log('Connected to AI Assistant service');
            
            return true;
        } catch (error) {
            console.error('Failed to connect to service:', error);
            this.connected = false;
            
            // Schedule reconnection
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                GLib.timeout_add(GLib.PRIORITY_DEFAULT, this.reconnectDelay, () => {
                    this.connect();
                    return GLib.SOURCE_REMOVE;
                });
            }
            
            return false;
        }
    }

    async sendRequest(endpoint, data = {}) {
        if (!this.connected) {
            throw new Error('Not connected to service');
        }

        try {
            // Use curl to send HTTP request over Unix socket
            const curl = Gio.Subprocess.new([
                'curl',
                '--unix-socket', SOCKET_PATH,
                '-X', 'POST',
                '-H', 'Content-Type: application/json',
                '-d', JSON.stringify(data),
                `http://localhost${endpoint}`
            ], Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE);

            const [, stdout, stderr] = await curl.communicate_utf8_async(null, null);
            
            if (curl.get_exit_status() === 0) {
                return JSON.parse(stdout);
            } else {
                throw new Error(`Request failed: ${stderr}`);
            }
        } catch (error) {
            console.error('Service request error:', error);
            throw error;
        }
    }

    disconnect() {
        this.connected = false;
        this._connection = null;
        console.log('Disconnected from AI Assistant service');
    }
}

/**
 * Chat dialog for interacting with the AI assistant
 */
const ChatDialog = GObject.registerClass(
class ChatDialog extends ModalDialog.ModalDialog {
    _init(serviceConnection) {
        super._init({
            styleClass: 'ai-chat-dialog',
        });

        this._serviceConnection = serviceConnection;
        this._chatHistory = [];

        this._createUI();
        this._connectSignals();
    }

    _createUI() {
        // Main container
        const mainBox = new St.BoxLayout({
            vertical: true,
            style_class: 'ai-chat-main-box',
        });

        // Header
        const headerBox = new St.BoxLayout({
            style_class: 'ai-chat-header',
        });

        const titleLabel = new St.Label({
            text: _('AI Assistant'),
            style_class: 'ai-chat-title',
        });

        const statusLabel = new St.Label({
            text: this._serviceConnection.connected ? _('Connected') : _('Disconnected'),
            style_class: this._serviceConnection.connected ? 'ai-status-connected' : 'ai-status-disconnected',
        });

        headerBox.add_child(titleLabel);
        headerBox.add_child(statusLabel);

        // Chat area
        this._chatScroll = new St.ScrollView({
            style_class: 'ai-chat-scroll',
            hscrollbar_policy: St.PolicyType.NEVER,
            vscrollbar_policy: St.PolicyType.AUTOMATIC,
        });

        this._chatBox = new St.BoxLayout({
            vertical: true,
            style_class: 'ai-chat-box',
        });

        this._chatScroll.set_child(this._chatBox);

        // Input area
        const inputBox = new St.BoxLayout({
            style_class: 'ai-chat-input-box',
        });

        this._textEntry = new St.Entry({
            style_class: 'ai-chat-entry',
            hint_text: _('Type your message...'),
            can_focus: true,
        });

        this._sendButton = new St.Button({
            style_class: 'ai-chat-send-button',
            label: _('Send'),
            can_focus: true,
        });

        inputBox.add_child(this._textEntry);
        inputBox.add_child(this._sendButton);

        // Assemble dialog
        mainBox.add_child(headerBox);
        mainBox.add_child(this._chatScroll);
        mainBox.add_child(inputBox);

        this.contentLayout.add_child(mainBox);

        // Add initial welcome message
        this._addMessage('assistant', _('Hello! I\'m your AI assistant. How can I help you today?'));
    }

    _connectSignals() {
        this._sendButton.connect('clicked', () => this._sendMessage());
        
        this._textEntry.connect('key-press-event', (entry, event) => {
            const symbol = event.get_key_symbol();
            if (symbol === Clutter.KEY_Return || symbol === Clutter.KEY_KP_Enter) {
                this._sendMessage();
                return Clutter.EVENT_STOP;
            }
            return Clutter.EVENT_PROPAGATE;
        });
    }

    async _sendMessage() {
        const message = this._textEntry.get_text().trim();
        if (!message) return;

        // Add user message to chat
        this._addMessage('user', message);
        this._textEntry.set_text('');

        // Show typing indicator
        const typingIndicator = this._addMessage('assistant', _('Typing...'));
        typingIndicator.add_style_class_name('ai-typing-indicator');

        try {
            // Send to service
            const response = await this._serviceConnection.sendRequest('/chat', {
                message: message,
                context: {
                    session_id: 'extension_session',
                    user_id: GLib.get_user_name()
                }
            });

            // Remove typing indicator
            typingIndicator.destroy();

            // Add assistant response
            this._addMessage('assistant', response.response);

            // Handle function calls if present
            if (response.function_calls && response.function_calls.length > 0) {
                this._handleFunctionCalls(response.function_calls);
            }

        } catch (error) {
            // Remove typing indicator
            typingIndicator.destroy();
            
            // Show error message
            this._addMessage('assistant', _('Sorry, I encountered an error. Please make sure the AI service is running.'));
            console.error('Chat error:', error);
        }

        // Scroll to bottom
        this._scrollToBottom();
    }

    _addMessage(role, content) {
        const messageBox = new St.BoxLayout({
            style_class: `ai-message-box ai-message-${role}`,
            vertical: true,
        });

        const messageLabel = new St.Label({
            text: content,
            style_class: `ai-message-label ai-message-${role}-label`,
        });
        messageLabel.clutter_text.set_line_wrap(true);
        messageLabel.clutter_text.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR);

        const timestampLabel = new St.Label({
            text: new Date().toLocaleTimeString(),
            style_class: 'ai-message-timestamp',
        });

        messageBox.add_child(messageLabel);
        messageBox.add_child(timestampLabel);

        this._chatBox.add_child(messageBox);
        
        return messageBox;
    }

    _handleFunctionCalls(functionCalls) {
        functionCalls.forEach(call => {
            const functionInfo = `🔧 ${call.name}(${JSON.stringify(call.arguments)})`;
            this._addMessage('system', _('Function called: ') + functionInfo);
        });
    }

    _scrollToBottom() {
        GLib.idle_add(GLib.PRIORITY_DEFAULT, () => {
            const adjustment = this._chatScroll.get_vscroll_bar().get_adjustment();
            adjustment.set_value(adjustment.get_upper() - adjustment.get_page_size());
            return GLib.SOURCE_REMOVE;
        });
    }

    vfunc_key_press_event(keyEvent) {
        if (keyEvent.keyval === Clutter.KEY_Escape) {
            this.close();
            return Clutter.EVENT_STOP;
        }
        return super.vfunc_key_press_event(keyEvent);
    }
});

/**
 * Main panel indicator
 */
const AIAssistantIndicator = GObject.registerClass(
class AIAssistantIndicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, _('AI Assistant'));

        // Service connection
        this._serviceConnection = new ServiceConnection();

        // Create panel icon
        this._icon = new St.Icon({
            icon_name: 'system-run-symbolic',
            style_class: 'system-status-icon',
        });
        this.add_child(this._icon);

        // Create menu
        this._createMenu();

        // Connect to service
        this._initializeServiceConnection();

        // Update icon based on connection status
        this._updateIcon();
    }

    _createMenu() {
        // Chat item
        this._chatItem = new PopupMenu.PopupMenuItem(_('Open Chat'));
        this._chatItem.connect('activate', () => this._openChat());
        this.menu.addMenuItem(this._chatItem);

        // Separator
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // Service status
        this._statusItem = new PopupMenu.PopupMenuItem(_('Service Status'), {
            reactive: false,
        });
        this.menu.addMenuItem(this._statusItem);

        // Available tools
        this._toolsItem = new PopupMenu.PopupMenuItem(_('Available Tools: Loading...'), {
            reactive: false,
        });
        this.menu.addMenuItem(this._toolsItem);

        // Separator
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // Settings
        const settingsItem = new PopupMenu.PopupMenuItem(_('Settings'));
        settingsItem.connect('activate', () => this._openSettings());
        this.menu.addMenuItem(settingsItem);

        // Emergency stop
        const emergencyItem = new PopupMenu.PopupMenuItem(_('Emergency Stop'));
        emergencyItem.connect('activate', () => this._emergencyStop());
        this.menu.addMenuItem(emergencyItem);
    }

    async _initializeServiceConnection() {
        try {
            await this._serviceConnection.connect();
            this._updateStatus();
            this._loadToolsInfo();
        } catch (error) {
            console.error('Failed to initialize service connection:', error);
            this._updateStatus();
        }

        // Set up periodic status updates
        this._statusUpdateId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 30, () => {
            this._updateStatus();
            return GLib.SOURCE_CONTINUE;
        });
    }

    async _updateStatus() {
        try {
            if (this._serviceConnection.connected) {
                const status = await this._serviceConnection.sendRequest('/status');
                this._statusItem.label.set_text(
                    _('Service: ') + status.status + _(', LLM: ') + status.llm_status
                );
            } else {
                this._statusItem.label.set_text(_('Service: Disconnected'));
            }
        } catch (error) {
            this._statusItem.label.set_text(_('Service: Error'));
            console.error('Status update error:', error);
        }

        this._updateIcon();
    }

    async _loadToolsInfo() {
        try {
            if (this._serviceConnection.connected) {
                const tools = await this._serviceConnection.sendRequest('/tools');
                this._toolsItem.label.set_text(_('Available Tools: ') + tools.count);
            } else {
                this._toolsItem.label.set_text(_('Available Tools: Unknown'));
            }
        } catch (error) {
            this._toolsItem.label.set_text(_('Available Tools: Error'));
            console.error('Tools info error:', error);
        }
    }

    _updateIcon() {
        if (this._serviceConnection.connected) {
            this._icon.set_icon_name('system-run-symbolic');
            this._icon.remove_style_class_name('ai-disconnected');
            this._icon.add_style_class_name('ai-connected');
        } else {
            this._icon.set_icon_name('system-run-symbolic');
            this._icon.remove_style_class_name('ai-connected');
            this._icon.add_style_class_name('ai-disconnected');
        }
    }

    _openChat() {
        if (!this._chatDialog) {
            this._chatDialog = new ChatDialog(this._serviceConnection);
        }
        this._chatDialog.open();
    }

    _openSettings() {
        // Open extension preferences
        try {
            Gio.Subprocess.new([
                'gnome-extensions', 'prefs', 'gnome-ai-assistant@example.com'
            ], Gio.SubprocessFlags.NONE);
        } catch (error) {
            console.error('Failed to open settings:', error);
        }
    }

    async _emergencyStop() {
        try {
            // Send emergency stop signal to service
            await this._serviceConnection.sendRequest('/emergency_stop');
            Main.notify(_('AI Assistant'), _('Emergency stop activated'));
        } catch (error) {
            console.error('Emergency stop error:', error);
            Main.notify(_('AI Assistant'), _('Failed to send emergency stop'));
        }
    }

    destroy() {
        if (this._statusUpdateId) {
            GLib.source_remove(this._statusUpdateId);
            this._statusUpdateId = null;
        }

        if (this._chatDialog) {
            this._chatDialog.destroy();
            this._chatDialog = null;
        }

        this._serviceConnection.disconnect();
        super.destroy();
    }
});

/**
 * Extension class
 */
export default class AIAssistantExtension extends Extension {
    enable() {
        console.log('Enabling AI Assistant extension');
        
        this._indicator = new AIAssistantIndicator();
        Main.panel.addToStatusArea(this.uuid, this._indicator);
        
        // Show welcome notification
        Main.notify(
            _('AI Assistant'),
            _('AI Assistant extension loaded. Click the icon to start chatting!')
        );
    }

    disable() {
        console.log('Disabling AI Assistant extension');
        
        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }
    }
}
