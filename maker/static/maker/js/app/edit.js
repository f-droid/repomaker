var categories = document.getElementById('rm-app-categories');
var categoryFormField = document.getElementById('id_category');
var categoryAddButton = document.getElementById('rm-app-category-add');
var categoryAddButtonLabel = categoryAddButton.getElementsByClassName('rm-app-category-text')[0];

init();

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
