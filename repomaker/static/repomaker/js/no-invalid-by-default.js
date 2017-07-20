// Source: https://gist.github.com/roshangautam/caefd856f9eb9e26033c0f71eebca837
(function() {
    'use strict';

    MaterialTextfield = window['MaterialTextfield'];

    /**
     * Handle lost focus.
     *
     * @private
     */
    MaterialTextfield.prototype.onBlur_ = function() {
        this.element_.classList.remove(this.CssClasses_.IS_FOCUSED);
        this.checkValidity();
    };
    /**
     * Handle change.
     *
     * @private
     */
    MaterialTextfield.prototype.onChange_ = function() {
        this.checkValidity();
    };

    /**
     * Handle class updates.
     *
     * @private
     */
    MaterialTextfield.prototype.updateClasses_ = function() {
        this.checkDisabled();
        this.checkDirty();
        var dirty = this.element_.classList.contains(this.CssClasses_.IS_DIRTY);
        var required = this.input_.required;
        if (!required || required && dirty) {
            this.checkValidity();
        }
        this.checkFocus();
    };
    /**
     * Enable text field.
     *
     * @public
     */
    MaterialTextfield.prototype.enable = function() {
        this.input_.disabled = false;
        this.updateClasses_();
        this.checkValidity();
    };
    MaterialTextfield.prototype['enable'] = MaterialTextfield.prototype.enable;

    /**
     * Initialize element.
     */
    MaterialTextfield.prototype.init = function() {
        if (this.element_) {
            this.label_ = this.element_.querySelector('.' + this.CssClasses_.LABEL);
            this.input_ = this.element_.querySelector('.' + this.CssClasses_.INPUT);
            if (this.input_) {
                if (this.input_.hasAttribute(
                        /** @type {string} */
                        (this.Constant_.MAX_ROWS_ATTRIBUTE))) {
                    this.maxRows = parseInt(this.input_.getAttribute(
                        /** @type {string} */
                        (this.Constant_.MAX_ROWS_ATTRIBUTE)), 10);
                    if (isNaN(this.maxRows)) {
                        this.maxRows = this.Constant_.NO_MAX_ROWS;
                    }
                }
                if (this.input_.hasAttribute('placeholder')) {
                    this.element_.classList.add(this.CssClasses_.HAS_PLACEHOLDER);
                }
                this.boundUpdateClassesHandler = this.updateClasses_.bind(this);
                this.boundFocusHandler = this.onFocus_.bind(this);
                this.boundBlurHandler = this.onBlur_.bind(this);
                this.boundResetHandler = this.onReset_.bind(this);
                this.boundChangeHandler = this.onChange_.bind(this);
                this.input_.addEventListener('input', this.boundUpdateClassesHandler);
                this.input_.addEventListener('focus', this.boundFocusHandler);
                this.input_.addEventListener('blur', this.boundBlurHandler);
                this.input_.addEventListener('reset', this.boundResetHandler);
                this.input_.addEventListener('change', this.boundChangeHandler);
                if (this.maxRows !== this.Constant_.NO_MAX_ROWS) {
                    // TODO: This should handle pasting multi line text.
                    // Currently doesn't.
                    this.boundKeyDownHandler = this.onKeyDown_.bind(this);
                    this.input_.addEventListener('keydown', this.boundKeyDownHandler);
                }
                var invalid = this.element_.classList.contains(this.CssClasses_.IS_INVALID);
                this.updateClasses_();
                this.element_.classList.add(this.CssClasses_.IS_UPGRADED);
                if (invalid) {
                    this.element_.classList.add(this.CssClasses_.IS_INVALID);
                }
                if (this.input_.hasAttribute('autofocus')) {
                    this.element_.focus();
                    this.checkFocus();
                }
            }
        }
    };
    // The component registers itself. It can assume componentHandler is available
    // in the global scope.
    componentHandler.registerUpgradedCallback(MaterialTextfield, function(textfield){});
})();
