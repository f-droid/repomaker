var buttonAdd = document.getElementById('rm-app-card-footer-action')

// Exceptions that can occur
var EXCEPTION_ALREADY_ADDED = '1'
var EXCEPTION_DATABASE_LOCKED = '2'

// IDs of resources
window.repoId = '0'
window.appRepoId = '0'
window.appId = '0'
window.element = 'null'

function addRemoteApp(event, repoId, appRepoId, appId) {
    // Prevent opening new page
    event.preventDefault()

    // Set global variables
    window.repoId = repoId
    window.appRepoId = appRepoId
    window.appId = appId
    window.element = 'rm-app-card-footer-action--' + appId

    var url = '/repo/' + repoId + '/app/remote/' + appRepoId + '/add_hl/' + appId
    buttonSetLoading()
    httpGet(url, remoteAppAdded)
}

function remoteAppAdded(responseText) {
    if ("True" === responseText) {
        buttonSetSuccessful()
    }
    else if (EXCEPTION_ALREADY_ADDED === responseText) {
        buttonSetFailed('The app already exists in your repo.')
    }
    else if (EXCEPTION_DATABASE_LOCKED === responseText) {
        buttonSetFailed('Please wait a moment, there is currently some background activity ongoing.')
    }
    else {
        buttonSetFailed('There was a problem with adding the app...')
    }
}

function buttonSetLoading() {
    // TODO: Implement https://gitlab.com/fdroid/repomaker/issues/41#states-of-adding
    setContentOfElement(window.element, 'Loading')
}

function buttonSetSuccessful() {
    setClassOfElement(window.element, 'rm-app-card-footer-action--successful')
    setContentOfElement(window.element, '<i class="material-icons">done</i>')
}

function buttonSetFailed(text) {
    setClassOfElement(window.element, 'rm-app-card-footer-action--failed')
    setContentOfElement(window.element, '<i class="material-icons">error</i>')
}

function setClassOfElement(element, myClass) {
    document.getElementById(element).className = myClass
}

function setContentOfElement(element, content) {
    console.debug(document.getElementById(element + '-button'))
    document.getElementById(element + '-button').innerHTML = content
}

function httpGet(url, callback) {
    var xmlHttp = new XMLHttpRequest()
    xmlHttp.onreadystatechange = function() {
        if (xmlHttp.readyState == 4 && xmlHttp.status == 200) {
            callback(xmlHttp.responseText)
        }
    }
    xmlHttp.open("POST", url, true) // true for asynchronous
    xmlHttp.setRequestHeader("X-CSRFToken", document.getElementsByName('csrfmiddlewaretoken')[0].value);
    xmlHttp.send(null)
}
