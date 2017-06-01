var buttonAdd = document.getElementById('rm-app-card-footer-action')

// Exceptions that can occur
var EXCEPTION_DATABASE_LOCKED = '1'

// TODO: Remove with https://gitlab.com/fdroid/repomaker/issues/93
var EXCEPTION_ALREADY_ADDED = '2'

// Apps to be added when user click "Done"
var appsToAdd = []

// Repo ID
window.repoId = '0'

function addRemoteApp(event, repoId, appRepoId, appId) {
    // Prevent opening new page
    event.preventDefault()

    if (window.repoId === '0') {
        window.repoId = repoId
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
}

function done(event) {
    if (appsToAdd.length === 0) {
        return
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

function buttonSetAdded(element) {
    setClassOfElement(element, 'rm-app-card-footer-action--successful')
    setContentOfElement(element + '-button', '<i class="material-icons">done</i>')
}

function buttonSetNormal(element) {
    setClassOfElement(element, 'rm-app-card-footer-action')
    // TODO: i18n
    setContentOfElement(element + '-button', 'Add')
}

function showError(text) {
    var element = 'rm-app-add-errors'
    setContentOfElement(element, text)
    setHiddenOfElement(element, false)
}

function setClassOfElement(element, myClass) {
    document.getElementById(element).className = myClass
}

function setContentOfElement(element, content) {
    document.getElementById(element).innerHTML = content
}

function setHiddenOfElement(element, hidden) {
    document.getElementById(element).hidden = hidden
}
