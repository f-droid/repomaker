var categories = document.getElementById('rm-app-categories');
var categoryFormField = document.getElementById('id_category');
var categoryAddButton = document.getElementById('rm-app-category-add');
if (categoryAddButton !== null) {
    var categoryAddButtonLabel = categoryAddButton.getElementsByClassName('rm-app-category-text')[0];
    init();
}

function init() {
    // hide category form field, so it is only visible without JavaScript
    categoryFormField.style.display = "none";

    // show category chips and add button
    categories.style.display = "initial";

    for (i = 0; i < categoryFormField.length; i++) {
        // find existing categories
        if (categoryFormField.options[i].selected) {
            // disable existing categories in add menu
            categoryId = categoryFormField.options[i].value
            document.getElementById('add_category_' + categoryId).disabled = true;
        }
    }

    updateCategoryAddButtonLabel();
}

function addCategory(categoryId) {
    for (i = 0; i < categoryFormField.length; i++) {
        // find clicked category in form field
        if (categoryFormField.options[i].value == categoryId) {
            if (categoryFormField.options[i].selected) return;
            // select clicked category
            categoryFormField.options[i].selected = true;
            // disable category in add menu
            document.getElementById('add_category_' + categoryId).disabled = true;
            // add clicked category to document
            addChip(categoryId, categoryFormField.options[i].text);
        }
    }
    updateCategoryAddButtonLabel();
}

function addChip(categoryId, categoryName) {
    // create chip
    var chip = document.createElement('span');
    chip.id = 'category_' + categoryId;
    chip.className = 'rm-app-category-chip';

    // add category name to chip
    var chipName = document.createElement('span');
    chipName.className = 'rm-app-category-text';
    chipName.appendChild(document.createTextNode(categoryName));
    chip.appendChild(chipName);

    // add remove button to chip
    var chipButton = document.createElement('button');
    chipButton.type = 'button';
    chipButton.className = 'mdl-chip__action';
    chipButton.onclick = function() { removeCategory(categoryId); };
    var chipButtonIcon = document.createElement('i');
    chipButtonIcon.className = 'material-icons';
    chipButtonIcon.appendChild(document.createTextNode('clear'));
    chipButton.appendChild(chipButtonIcon);
    chip.appendChild(chipButton);

    // add chip to categories
    categories.insertBefore(chip, categories.firstChild);
}

function updateCategoryAddButtonLabel() {
    for (i = 0; i < categoryFormField.length; i++) {
        if (categoryFormField.options[i].selected) {
            categoryAddButtonLabel.style.display = "none";
            return;
        }
    }
    categoryAddButtonLabel.style.display = "initial";
}

function removeCategory(categoryId) {
    for (i = 0; i < categoryFormField.length; i++) {
        // find clicked category in form field
        if (categoryFormField.options[i].value == categoryId) {
            // de-select clicked category
            categoryFormField.options[i].selected = false;
            // enable category in add menu
            document.getElementById('add_category_' + categoryId).disabled = false;
            // remove clicked category from document
            document.getElementById('category_' + categoryId).remove();
        }
    }
    updateCategoryAddButtonLabel();
}

/**
 * Delete things in the background
 */

// Divs holding the repo and app id
var DIV_REPO_ID = 'rm-repo-id'
var DIV_APP_ID = 'rm-app-id'

function defaultDeleteConfirm(dialog, elementDelete, url, callback) {
    // Build request
    var request = new XMLHttpRequest()
    request.open('POST', url, true)
    request.setRequestHeader('X-CSRFToken',
        document.getElementsByName('csrfmiddlewaretoken')[0].value)
    request.onreadystatechange = function() {
        if (request.readyState === 4) {
            if (request.status === 200) {
                callback(elementDelete)
                dialog.close()
                return
            }
            dialog.close()
            alert(interpolate(
                gettext('Sorry, there was an error deleting it: %s'), [request.status]))
        }
    }
    request.send()
}

function defaultDeleteCancel(dialog, elementDelete) {
    dialog.close()
}

/**
 * Screenshots
 */
function registerDeleteListenerScreenshot(screenshotDelete) {
    if (screenshotDelete !== null) {
        screenshotDelete.addEventListener('click', function(event) {
            // Prevent opening separate page
            event.preventDefault()

            showMdlDialog(gettext('Delete Screenshot'),
                gettext('Are you sure you want to delete this screenshot from your package?'),
                screenshotDeleteConfirm, screenshotDeleteCancel,
                screenshotDelete
                )
        })
    }
}

function registerDeleteListenerAllScreenshots() {
    var screenshots = document.getElementsByClassName('rm-app-screenshot')
    for (var i = 0; i < screenshots.length; i++) {
        var screenshot = screenshots[i]
        registerDeleteListenerScreenshot(screenshot.querySelector('.rm-app-screenshot-delete'))
    }
}
registerDeleteListenerAllScreenshots()

function screenshotDeleteConfirm(dialog, screenshotDelete) {
    var repoId = document.getElementById(DIV_REPO_ID).dataset.id
    var appId = document.getElementById(DIV_APP_ID).dataset.id
    var screenshotId = screenshotDelete.dataset.id

    defaultDeleteConfirm(dialog, screenshotDelete,
        Urls.screenshot_delete(repoId, appId, screenshotId), screenshotDeleted)
}

function screenshotDeleteCancel(dialog, screenshotDelete) {
    defaultDeleteCancel(dialog, screenshotDelete)
}

function screenshotDeleted(screenshotDelete) {
    var screenshotContainer = screenshotDelete.parentElement  // TODO getElementById
    var screenshotsContainer = screenshotContainer.parentElement  // TODO getElementById

    screenshotsContainer.removeChild(screenshotContainer)
}

/**
 * Feature Graphic
 */
function registerDeleteListenerFeatureGraphic() {
    var featureGraphicDelete = document.querySelector('.rm-app-feature-graphic-delete')
    if (featureGraphicDelete !== null) {
        featureGraphicDelete.addEventListener('click', function(event) {
            // Prevent opening separate page
            event.preventDefault()

            showMdlDialog(gettext('Delete Feature Graphic'),
                gettext('Are you sure you want to delete the feature graphic from your package?'),
                featureGraphicDeleteConfirm, featureGraphicDeleteCancel,
                featureGraphicDelete
                )
        })
    }
}
registerDeleteListenerFeatureGraphic()

function featureGraphicDeleteConfirm(dialog, featureGraphicDelete) {
    var repoId = document.getElementById(DIV_REPO_ID).dataset.id
    var appId = document.getElementById(DIV_APP_ID).dataset.id

    defaultDeleteConfirm(dialog, featureGraphicDelete, Urls.delete_feature_graphic(repoId, appId),
        featureGraphicDeleted)
}

function featureGraphicDeleteCancel(dialog, featureGraphicDelete) {
    defaultDeleteCancel(dialog, featureGraphicDelete)
}

function featureGraphicDeleted(featureGraphicDelete) {
    var featureGraphicContainer = featureGraphicDelete.parentElement  // TODO getElementById
    var featureGraphicImg = document.getElementById('rm-app-feature-graphic-img')

    // Delete image and delete button from DOM
    featureGraphicContainer.removeChild(featureGraphicImg)
    featureGraphicContainer.removeChild(featureGraphicDelete)
}

/**
 * APKs
 */
function registerDeleteListenerApk(apkDelete) {
    if (apkDelete !== null) {
        apkDelete.addEventListener('click', function(event) {
            // Prevent opening separate page
            event.preventDefault()

            showMdlDialog(gettext('Delete Version'),
                gettext('Are you sure you want to delete this version from your package?'),
                apkDeleteConfirm, apkDeleteCancel,
                apkDelete
                )
        })
    }
}

function registerDeleteListenerAllApks() {
    var apks = document.getElementsByClassName('rm-app-versions-item')
    for (var i = 0; i < apks.length; i++) {
        var apk = apks[i]
        registerDeleteListenerApk(apk.querySelector('.rm-app-versions-item-delete'))
    }
}
registerDeleteListenerAllApks()

function apkDeleteConfirm(dialog, apkDelete) {
    var repoId = document.getElementById(DIV_REPO_ID).dataset.id
    var appId = document.getElementById(DIV_APP_ID).dataset.id
    var apkPointerId = apkDelete.dataset.id

    defaultDeleteConfirm(dialog, apkDelete, Urls.apk_delete(repoId, appId, apkPointerId),
        apkDeleted)
}

function apkDeleteCancel(dialog, apkDelete) {
    defaultDeleteCancel(dialog, apkDelete)
}

function apkDeleted(apkDelete) {
    var apkLi = apkDelete.parentElement  // TODO getElementById
    var apkUl = apkLi.parentElement  // TODO getElementById

    apkUl.removeChild(apkLi)
}

/**
 * Creates MDL dialog
 */
function showMdlDialog(header, text, confirm, cancel, elementDelete) {
    var dialog = document.createElement('dialog')
    dialog.classList.add('mdl-dialog')

    var dialogHeader = document.createElement('h4')
    dialogHeader.classList.add('mdl-dialog__title')
    dialogHeader.innerText = header
    dialog.appendChild(dialogHeader)

    var dialogContent = document.createElement('div')
    dialogContent.classList.add('mdl-dialog__content')

    var dialogContentParagraph = document.createElement('p')
    dialogContentParagraph.innerText = text
    dialogContent.appendChild(dialogContentParagraph)

    dialog.appendChild(dialogContent)

    var dialogActions = document.createElement('div')
    dialogActions.classList.add('mdl-dialog__actions')

    var dialogActionsConfirm = document.createElement('button')
    dialogActionsConfirm.classList.add('mdl-button')
    dialogActionsConfirm.classList.add('rm-dialog-confirm')
    dialogActionsConfirm.type = 'button'
    dialogActionsConfirm.innerText = gettext('Confirm')
    dialogActions.appendChild(dialogActionsConfirm)

    var dialogActionsCancel = document.createElement('button')
    dialogActionsCancel.classList.add('mdl-button')
    dialogActionsCancel.classList.add('rm-dialog-cancel')
    dialogActionsCancel.type = 'button'
    dialogActionsCancel.innerText = gettext('Cancel')
    dialogActions.appendChild(dialogActionsCancel)

    dialog.appendChild(dialogActions)

    // Upgrade element according to https://getmdl.io/started/index.html#dynamic
    componentHandler.upgradeElement(dialog)

    document.querySelector('body').appendChild(dialog)

    if (!dialog.showModal) {
        dialogPolyfill.registerDialog(dialog)
    }
    dialog.querySelector('.rm-dialog-confirm').addEventListener('click', function() {
        confirm(dialog, elementDelete)
    });
    dialog.querySelector('.rm-dialog-cancel').addEventListener('click', function() {
        cancel(dialog, elementDelete)
    });

    dialog.showModal()
}