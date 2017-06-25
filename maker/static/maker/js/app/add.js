/**
 * Add
 */
var buttonAdd = document.getElementById('rm-app-card-footer-action')

// Exceptions that can occur
var EXCEPTION_DATABASE_LOCKED = '1'

// TODO: Remove with https://gitlab.com/fdroid/repomaker/issues/93
var EXCEPTION_ALREADY_ADDED = '2'

// Apps to be added when user click "Done"
var appsToAdd = []

// Keys for HTML5 session storage
var sessionStorageKeyApps = 'rmAppsToAdd'
var sessionStorageKeyRepo = 'rmRepo'

// Repo ID
window.repoId = '0'

// Get apps to add from local storage
if (typeof(Storage) !== "undefined") {
    var sessionStorageAppsToAdd = JSON.parse(sessionStorage.getItem(sessionStorageKeyApps))
    if (sessionStorageAppsToAdd !== null && sessionStorageAppsToAdd.length !== 0 && appsToAdd.length === 0) {
        appsToAdd = sessionStorageAppsToAdd
        markAppsToAdd()
        updateAppsToAddCount()
    }
}

function addRemoteApp(event, repoId, appRepoId, appId) {
    // Prevent opening new page
    event.preventDefault()

    if (window.repoId === '0') {
        window.repoId = repoId
        sessionStorage.setItem(sessionStorageKeyRepo, repoId)
    }
    else if (window.repoId !== repoId) {
        throw new Error('Repository ID where the apps should be added to differs')
    }

    var app = {
        appRepoId: appRepoId,
        appId: appId
    }
    var element = 'rm-app-card-footer-action--' + appId
    var appAlreadyAdded = false

    // Check if app is already to be added
    for(var i = 0; i < appsToAdd.length; i++) {
        if (appsToAdd[i].appRepoId == appRepoId && appsToAdd[i].appId == appId) {
            appAlreadyAdded = true
            appsToAdd.splice(i, 1)
            buttonSetNormal(element)
            break
        }
    }
    if (!appAlreadyAdded) {
        appsToAdd.push(app)
        buttonSetAdded(element)
    }

    // Synchronize JS with session storage
    if (typeof(Storage) !== "undefined") {
        sessionStorage.setItem(sessionStorageKeyApps, JSON.stringify(appsToAdd))
        updateAppsToAddCount()
    }
}

function back(event) {
    if (appsToAdd.length === 0) {
        return
    }
    if (window.repoId === '0') {
        window.repoId = sessionStorage.getItem(sessionStorageKeyRepo)
    }
    // Prevent opening new page
    event.preventDefault()

    var url = '/repo/' + window.repoId + '/app/add/'
    var request = new XMLHttpRequest()
    request.onreadystatechange = function() {
        if (request.readyState === 4) {
            appsAdded(request)
        }
    }
    request.open("POST", url, true) // true for asynchronous
    request.setRequestHeader("X-CSRFToken", document.getElementsByName('csrfmiddlewaretoken')[0].value)
    request.setRequestHeader('X-REQUESTED-WITH', 'XMLHttpRequest') // For Django's request.is_ajax()
    request.send(JSON.stringify(appsToAdd))
}

function appsAdded(request) {
    if (request.status === 204) {
        // Clear session storage list
        if (typeof(Storage) !== "undefined") {
            sessionStorage.removeItem(sessionStorageKeyApps)
            sessionStorage.removeItem(sessionStorageKeyRepo)
        }

        window.location = '/repo/' + window.repoId
    }
    else if (request.status === 400 && request.responseText === EXCEPTION_ALREADY_ADDED){
        showError('One of the apps already exists in your repo.')
    }
    else if (request.status === 500 && request.responseText === EXCEPTION_DATABASE_LOCKED) {
        showError('Please wait a moment, there is currently some background activity ongoing.')
    }
    else {
        showError('There was a problem with adding the app.')
    }
}

function markAppsToAdd() {
    for (var i = 0; i < appsToAdd.length; i++) {
        var element = 'rm-app-card-footer-action--' + appsToAdd[i]['appId']
        buttonSetAdded(element)
    }
}

function updateAppsToAddCount() {
    var count = appsToAdd.length
    var countContainer = document.querySelector('.rm-repo-add-toolbar-count')
    countContainer.hidden = false
    var countText = document.getElementById('rm-repo-add-toolbar-count-text')
    if (count === 1) {
        countText.textContent = '1 app to be added'
    }
    else if (count > 1) {
        countText.textContent = count + ' apps to be added'
    }
    else {
        countContainer.hidden = true
    }
}

function clearAppsToAdd(event) {
    // Clear session storage list
    if (typeof(Storage) !== "undefined") {
        sessionStorage.removeItem(sessionStorageKeyApps)
    }
}

function buttonSetAdded(element) {
    setClassOfElement(element, 'rm-app-card-footer-action--successful')
    setContentOfElement(element + '-button', '<i class="material-icons">done</i>')
}

function buttonSetNormal(element) {
    setClassOfElement(element, 'rm-app-card-footer-action')
    setContentOfElement(element + '-button', 'Add')
}

function showError(text) {
    var element = 'rm-app-add-errors'
    setContentOfElement(element, text)
    setHiddenOfElement(element, false)
}

/**
 * Miscellaneous
 */
function setClassOfElement(element, myClass) {
    element = document.getElementById(element)
    if (element !== null) {
        element.className = myClass
    }
}

function setContentOfElement(element, content) {
    element = document.getElementById(element)
    if (element !== null) {
        element.innerHTML = content
    }
}

function setHiddenOfElement(element, hidden) {
    if (typeof element === 'string') {
        element = document.getElementById(element)
    }
    if (element !== null) {
        element.hidden = hidden
    }
}

/**
 * Search
 */
var searchInput = document.querySelector('.rm-app-add-filters-search-input')
var searchClear = document.querySelector('.rm-app-add-filters-search-clear')

// Set hidden or not at page load
setHiddenOfElement(searchClear, (searchInput.value.length === 0))

// Set hidden or not on input
searchInput.addEventListener("input", function() {
    setHiddenOfElement(searchClear, (searchInput.value.length === 0))
})
