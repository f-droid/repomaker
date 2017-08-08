/**
 * Add
 */
var buttonAdd = document.getElementById('rm-app-card-footer-action')

// Apps to be added when user click "Done"
var appsToAdd = []

// Keys for HTML5 session storage
var sessionStorageKeyApps = 'rmAppsToAdd'
var sessionStorageKeyRepo = 'rmRepo'
var sessionStorageKeyReferrer = 'rmReferrer'

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
    var sessionStorageRepo = JSON.parse(sessionStorage.getItem(sessionStorageKeyRepo))
    if (sessionStorageRepo !== null && sessionStorageRepo.length !== 0 && window.repoId === 0) {
        window.repoId = sessionStorageRepo
    }
}

function addRemoteApp(event, repoId, appRepoId, appId, remoteAddUrl) {
    // Prevent opening new page
    event.preventDefault()

    // Prevent opening app details
    event.stopPropagation()

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
            if (!remoteAddUrl) {
                appsToAdd.splice(i, 1)
            }
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

    if (remoteAddUrl) {
        location.href = remoteAddUrl
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

    var url = Urls.add_app(window.repoId)
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

        window.location = Urls.repo(window.repoId)
    }
    else {
        showError(request.responseText)
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
    if (countContainer === null) {
        return
    }
    countContainer.hidden = false
    var countText = document.getElementById('rm-repo-add-toolbar-count-text')
    if (count > 0) {
        countText.textContent =
            interpolate(ngettext('%s app added', '%s apps added', count), [count])
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
    addClassToElement(element, 'rm-app-card-footer-action--successful')
    setContentOfElement(element + '-button', '<i class="material-icons">done</i>')
}

function buttonSetNormal(element) {
    setClassOfElement(element, 'rm-app-card-footer-action')
    setContentOfElement(element + '-button', gettext('Add'))
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
function addClassToElement(element, myClass) {
    element = document.getElementById(element)
    if (element !== null) {
        element.classList.add(myClass)
    }
}
function removeClassFromElement(element, myClass) {
    element = document.getElementById(element)
    if (element !== null) {
        element.classList.remove(myClass)
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
 * Pagination
 */
var mdlBody = document.querySelector('.mdl-layout__content')
var pagination = document.querySelector('.rm-pagination')

mdlBody.addEventListener("scroll", function () {
    if (mdlBody.scrollHeight - window.innerHeight -
            mdlBody.scrollTop <= 800) {
        if (pagination !== null) {
            handlePagination(jsonHtmlRelation, '.rm-app-add-apps', markAppsToAdd)
        }
    }
}, false)

window.onload = function () {
    // Check if pagination is already visible at first page load
    if (pagination !== null && isVisible(pagination)) {
        handlePagination(jsonHtmlRelation, '.rm-app-add-apps', markAppsToAdd)
    }
}

var jsonHtmlRelation = {
    'rm-app-card-categories': 'categories',
    'rm-app-card-description': 'description',
    'rm-app-card-footer-action': 'id',
    'rm-app-card-left': 'icon',
    'rm-app-card-summary': 'summary',
    'rm-app-card-title': 'name',
    'rm-app-card-updated': 'updated',
    'rm-app-card--apps-add': 'id',
}

/**
 * Search
 */
var searchInput = document.querySelector('.rm-app-add-filters-search-input')
var searchClear = document.querySelector('.rm-app-add-filters-search-clear')

// Set hidden or not at page load
if (searchInput !== null) {
    setHiddenOfElement(searchClear, (searchInput.value.length === 0))

    // Set hidden or not on input
    searchInput.addEventListener("input", function() {
        setHiddenOfElement(searchClear, (searchInput.value.length === 0))
    })
}
