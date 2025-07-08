/**
 * Permission dialog component for AI Assistant Extension
 */

import GObject from 'gi://GObject';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';

import * as ModalDialog from 'resource:///org/gnome/shell/ui/modalDialog.js';

const PermissionLevel = {
    DENY: 'deny',
    ALLOW_ONCE: 'allow_once',
    ALLOW_SESSION: 'allow_session',
    ALLOW_PERMANENT: 'allow_permanent'
};

const RiskLevel = {
    LOW: 'low',
    MEDIUM: 'medium',
    HIGH: 'high',
    CRITICAL: 'critical'
};

const PermissionDialog = GObject.registerClass({
    Signals: {
        'permission-granted': {
            param_types: [GObject.TYPE_STRING] // permission level
        },
        'permission-denied': {}
    },
}, class PermissionDialog extends ModalDialog.ModalDialog {
    _init(permissionRequest) {
        super._init({ 
            styleClass: 'ai-permission-dialog',
            destroyOnClose: true
        });

        this._permissionRequest = permissionRequest;
        this._buildUI();
        this._setupEventHandlers();
    }

    _buildUI() {
        // Main container
        this._container = new St.BoxLayout({
            vertical: true,
            style_class: 'ai-permission-container'
        });

        // Header with icon and title
        this._header = new St.BoxLayout({
            style_class: 'ai-permission-header',
            vertical: false
        });

        this._icon = new St.Icon({
            icon_name: this._getIconForRiskLevel(this._permissionRequest.risk_level),
            style_class: `ai-permission-icon risk-${this._permissionRequest.risk_level}`,
            icon_size: 48
        });

        this._titleBox = new St.BoxLayout({
            vertical: true,
            x_expand: true
        });

        this._titleLabel = new St.Label({
            text: 'Permission Required',
            style_class: 'ai-permission-title'
        });

        this._subtitleLabel = new St.Label({
            text: `${this._permissionRequest.tool_name} wants to ${this._permissionRequest.action}`,
            style_class: 'ai-permission-subtitle'
        });

        this._titleBox.add_child(this._titleLabel);
        this._titleBox.add_child(this._subtitleLabel);

        this._header.add_child(this._icon);
        this._header.add_child(this._titleBox);

        // Description
        this._descriptionLabel = new St.Label({
            text: this._permissionRequest.description || 'This action requires permission to proceed.',
            style_class: 'ai-permission-description'
        });
        this._descriptionLabel.clutter_text.set_line_wrap(true);

        // Risk assessment
        this._riskBox = new St.BoxLayout({
            style_class: `ai-permission-risk risk-${this._permissionRequest.risk_level}`,
            vertical: false
        });

        this._riskIcon = new St.Icon({
            icon_name: this._getRiskIcon(this._permissionRequest.risk_level),
            icon_size: 16
        });

        this._riskLabel = new St.Label({
            text: `Risk Level: ${this._permissionRequest.risk_level.toUpperCase()}`,
            style_class: 'ai-permission-risk-label'
        });

        this._riskBox.add_child(this._riskIcon);
        this._riskBox.add_child(this._riskLabel);

        // Required capabilities
        if (this._permissionRequest.required_capabilities && 
            this._permissionRequest.required_capabilities.length > 0) {
            
            this._capabilitiesLabel = new St.Label({
                text: 'Required Capabilities:',
                style_class: 'ai-permission-capabilities-title'
            });

            this._capabilitiesList = new St.BoxLayout({
                vertical: true,
                style_class: 'ai-permission-capabilities-list'
            });

            for (const capability of this._permissionRequest.required_capabilities) {
                const capItem = new St.BoxLayout({
                    vertical: false,
                    style_class: 'ai-permission-capability-item'
                });

                const capIcon = new St.Icon({
                    icon_name: 'emblem-important-symbolic',
                    icon_size: 12
                });

                const capLabel = new St.Label({
                    text: this._formatCapability(capability),
                    style_class: 'ai-permission-capability-label'
                });

                capItem.add_child(capIcon);
                capItem.add_child(capLabel);
                this._capabilitiesList.add_child(capItem);
            }
        }

        // Parameters (if any)
        if (this._permissionRequest.parameters && 
            Object.keys(this._permissionRequest.parameters).length > 0) {
            
            this._parametersLabel = new St.Label({
                text: 'Parameters:',
                style_class: 'ai-permission-parameters-title'
            });

            this._parametersBox = new St.BoxLayout({
                vertical: true,
                style_class: 'ai-permission-parameters'
            });

            for (const [key, value] of Object.entries(this._permissionRequest.parameters)) {
                const paramLabel = new St.Label({
                    text: `${key}: ${value}`,
                    style_class: 'ai-permission-parameter'
                });
                this._parametersBox.add_child(paramLabel);
            }
        }

        // Remember choice checkbox
        this._rememberBox = new St.BoxLayout({
            vertical: false,
            style_class: 'ai-permission-remember'
        });

        // Note: GNOME Shell doesn't have a built-in checkbox, so we'll use a toggle button
        this._rememberToggle = new St.Button({
            style_class: 'ai-permission-remember-toggle',
            toggle_mode: true,
            child: new St.Icon({
                icon_name: 'object-select-symbolic',
                icon_size: 16
            })
        });

        this._rememberLabel = new St.Label({
            text: 'Remember this decision',
            style_class: 'ai-permission-remember-label'
        });

        this._rememberBox.add_child(this._rememberToggle);
        this._rememberBox.add_child(this._rememberLabel);

        // Buttons
        this._buttonBox = new St.BoxLayout({
            style_class: 'ai-permission-buttons',
            vertical: false,
            x_align: Clutter.ActorAlign.END
        });

        this._denyButton = new St.Button({
            style_class: 'ai-permission-button deny-button',
            label: 'Deny'
        });

        this._allowOnceButton = new St.Button({
            style_class: 'ai-permission-button allow-once-button',
            label: 'Allow Once'
        });

        this._allowSessionButton = new St.Button({
            style_class: 'ai-permission-button allow-session-button',
            label: 'Allow for Session'
        });

        this._allowAlwaysButton = new St.Button({
            style_class: 'ai-permission-button allow-always-button',
            label: 'Always Allow'
        });

        // Only show "Always Allow" for low risk operations
        if (this._permissionRequest.risk_level === RiskLevel.LOW) {
            this._buttonBox.add_child(this._allowAlwaysButton);
        }

        this._buttonBox.add_child(this._allowSessionButton);
        this._buttonBox.add_child(this._allowOnceButton);
        this._buttonBox.add_child(this._denyButton);

        // Assemble the dialog
        this._container.add_child(this._header);
        this._container.add_child(this._descriptionLabel);
        this._container.add_child(this._riskBox);

        if (this._capabilitiesLabel) {
            this._container.add_child(this._capabilitiesLabel);
            this._container.add_child(this._capabilitiesList);
        }

        if (this._parametersLabel) {
            this._container.add_child(this._parametersLabel);
            this._container.add_child(this._parametersBox);
        }

        this._container.add_child(this._rememberBox);
        this._container.add_child(this._buttonBox);

        this.contentLayout.add_child(this._container);
    }

    _setupEventHandlers() {
        this._denyButton.connect('clicked', () => {
            this._handlePermissionChoice(PermissionLevel.DENY);
        });

        this._allowOnceButton.connect('clicked', () => {
            this._handlePermissionChoice(PermissionLevel.ALLOW_ONCE);
        });

        this._allowSessionButton.connect('clicked', () => {
            this._handlePermissionChoice(PermissionLevel.ALLOW_SESSION);
        });

        if (this._allowAlwaysButton) {
            this._allowAlwaysButton.connect('clicked', () => {
                this._handlePermissionChoice(PermissionLevel.ALLOW_PERMANENT);
            });
        }

        this._rememberToggle.connect('clicked', () => {
            const isToggled = this._rememberToggle.get_checked();
            this._rememberToggle.child.icon_name = isToggled ? 
                'object-select-symbolic' : 'checkbox-symbolic';
        });

        // Auto-deny after timeout for high-risk operations
        if (this._permissionRequest.risk_level === RiskLevel.HIGH || 
            this._permissionRequest.risk_level === RiskLevel.CRITICAL) {
            
            this._timeout = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 30, () => {
                this._handlePermissionChoice(PermissionLevel.DENY);
                return GLib.SOURCE_REMOVE;
            });
        }
    }

    _handlePermissionChoice(level) {
        if (this._timeout) {
            GLib.source_remove(this._timeout);
            this._timeout = null;
        }

        const remember = this._rememberToggle.get_checked();
        
        if (level === PermissionLevel.DENY) {
            this.emit('permission-denied');
        } else {
            // If remember is checked and it's not "allow once", upgrade the permission level
            if (remember && level === PermissionLevel.ALLOW_ONCE) {
                level = PermissionLevel.ALLOW_SESSION;
            } else if (remember && level === PermissionLevel.ALLOW_SESSION) {
                level = PermissionLevel.ALLOW_PERMANENT;
            }
            
            this.emit('permission-granted', level);
        }

        this.close();
    }

    _getIconForRiskLevel(riskLevel) {
        switch (riskLevel) {
            case RiskLevel.LOW:
                return 'dialog-information-symbolic';
            case RiskLevel.MEDIUM:
                return 'dialog-warning-symbolic';
            case RiskLevel.HIGH:
                return 'dialog-error-symbolic';
            case RiskLevel.CRITICAL:
                return 'security-high-symbolic';
            default:
                return 'dialog-question-symbolic';
        }
    }

    _getRiskIcon(riskLevel) {
        switch (riskLevel) {
            case RiskLevel.LOW:
                return 'emblem-default-symbolic';
            case RiskLevel.MEDIUM:
                return 'dialog-warning-symbolic';
            case RiskLevel.HIGH:
                return 'dialog-error-symbolic';
            case RiskLevel.CRITICAL:
                return 'security-high-symbolic';
            default:
                return 'dialog-question-symbolic';
        }
    }

    _formatCapability(capability) {
        // Convert capability names to human-readable format
        const capabilityNames = {
            'file_access': 'Access files and directories',
            'network_access': 'Access network and internet',
            'system_control': 'Control system settings',
            'media_control': 'Control media playback',
            'desktop_control': 'Control desktop environment',
            'application_launch': 'Launch applications',
            'external_services': 'Access external services',
            'data_collection': 'Collect system data',
            'user_data': 'Access user data',
            'camera_access': 'Access camera',
            'microphone_access': 'Access microphone',
            'location_access': 'Access location data'
        };

        return capabilityNames[capability] || capability.replace('_', ' ');
    }

    destroy() {
        if (this._timeout) {
            GLib.source_remove(this._timeout);
            this._timeout = null;
        }
        super.destroy();
    }
});

// Factory function to create permission dialogs
export function showPermissionDialog(permissionRequest) {
    return new Promise((resolve, reject) => {
        const dialog = new PermissionDialog(permissionRequest);
        
        dialog.connect('permission-granted', (dialog, level) => {
            resolve(level);
        });
        
        dialog.connect('permission-denied', () => {
            resolve(PermissionLevel.DENY);
        });
        
        dialog.open();
    });
}
