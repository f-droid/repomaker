// Source: http://html5demos.com/dnd-upload
var holders = [
    document.getElementById('rm-dnd-holder--screenshots'),
    document.getElementById('rm-dnd-holder--apks'),
    document.getElementById('rm-dnd-holder-2--apks'),
    document.getElementById('rm-dnd-holder--feature-graphic'),
]

function uploadFiles(element, files) {
    var type = element.id.split("--").pop()
    var formData = new FormData()
    for (var i = 0; i < files.length; i++) {
        if ((type == 'screenshots' || type == 'feature-graphic') && !isImage(files[i])) {
            showError(element, gettext('You can only upload images here.'))
            return
        }
        formData.append(type, files[i])
    }
    var request = new XMLHttpRequest()
    request.open('POST', '', true) // true for asynchronous
    request.setRequestHeader('X-CSRFToken', document.getElementsByName('csrfmiddlewaretoken')[0].value)
    request.setRequestHeader('X-REQUESTED-WITH', 'XMLHttpRequest') // For Django's request.is_ajax()
    request.setRequestHeader('RM-Background-Type', type) // Needed to distinguish
    request.onloadstart = uploadStarted(element, files)
    request.upload.onprogress = function (event) {
        updateProgress(element, event)
    }
    request.onreadystatechange = function() {
        if (request.readyState === 4) {
            uploadFinished(request, element, type, files)
        }
    }
    request.send(formData)
}

if ('draggable' in document.createElement('span') && !!window.FormData) {
    showDndTexts()
    holders.forEach(function(holder) {
        if (holder != null) {
            holder.ondragover = function () {
                return onDragOver(this)
            }
            holder.ondragleave = function () {
                return onDragLeave(this)
            }
            holder.ondrop = function (event) {
                return onDrop(this, event)
            }
            holder.onchange = function () {
                return onChange(this)
            }
        }
    })
}

function onDragOver(element) {
    element.classList.add('rm-dnd-hover')
    return false
}

function onDragLeave(element) {
    element.classList.remove('rm-dnd-hover')
    return false
}

function onDrop(element, event) {
    fromHoverToLoading(element.classList)
    uploadFiles(element, event.dataTransfer.files)
    return false
}

function onChange(element) {
    fileElement = element.getElementsByTagName('input')[0]
    if (fileElement == null) return false;

    fromHoverToLoading(element.classList)
    uploadFiles(element, fileElement.files)
    fileElement.value = null  // reset files to not upload twice

    return false
}

function fromHoverToLoading(classList) {
    classList.remove('rm-dnd-hover')
    classList.add('rm-dnd-loading')
}

function uploadStarted(element, files) {
    var loadingElement = document.getElementById(element.id + '--loading')
    element.hidden = true
    loadingElement.hidden = false
    var loadingElementTitle = document.getElementById(loadingElement.id + '-title')
    loadingElementTitle.textContent =
        interpolate(ngettext('Uploading %s file...', 'Uploading %s files...', files.length), [files.length])
}

function updateProgress(element, event) {
    if (event.lengthComputable) {
        var progress = (event.loaded / event.total) * 100
        var progressBar = document.querySelector('.rm-dnd-progress')
        progressBar.MaterialProgress.setProgress(progress)
    }
}

function uploadFinished(request, element, type, files) {
    if (type === 'screenshots' && request.status === 200) {
        var response = JSON.parse(request.responseText)
        addScreenshots(element, response)
    }
    else if (type === 'feature-graphic' && request.status === 200) {
        var response = JSON.parse(request.responseText)
        setFeatureGraphic(element, response)
    }
    else if (type === 'apks' && request.status === 200) {
        var response = JSON.parse(request.responseText)
        addApks(element, response)
    }
    else if (request.status === 204) {
        location.reload()
    }
    else {
        showError(element, request.responseText)
    }
}

function addScreenshots(dndField, response) {
    var screenshotsContainer = dndField.parentElement // TODO getElementById
    var repo = response['repo']
    var app = response['app']
    var screenshots = response['screenshots']
    for (var i = 0; i < screenshots.length; i++) {
        var id = screenshots[i]['id']
        var url = screenshots[i]['url']
        var screenshotDiv = document.createElement('div')
        screenshotDiv.classList.add('rm-app-screenshot')

        var screenshotDelete = document.createElement('a')
        screenshotDelete.href = Urls.screenshot_delete(repo, app, id)
        screenshotDelete.classList.add('rm-app-screenshot-delete')
        screenshotDelete.dataset.id = id

        var screenshotDeleteButton = document.createElement('button')
        screenshotDeleteButton.type = 'button'
        screenshotDeleteButton.classList.add('mdl-js-button')

        var screenshotDeleteButtonContent = document.createElement('i')
        screenshotDeleteButtonContent.innerText = 'delete'

        screenshotDeleteButton.appendChild(screenshotDeleteButtonContent)
        screenshotDelete.appendChild(screenshotDeleteButton)

        var screenshotImg = document.createElement('img')
        screenshotImg.src = url

        screenshotDiv.appendChild(screenshotDelete)
        screenshotDiv.appendChild(screenshotImg)
        screenshotsContainer.appendChild(screenshotDiv)
        registerDeleteListenerScreenshot(screenshotDelete)
    }
    resetDndField(dndField)
}

function setFeatureGraphic(dndField, response) {
    var featureGraphicContainer = dndField.parentElement // TODO getElementById
    var repo = response['repo']
    var app = response['app']
    var featureGraphicUrl = response['feature-graphic']

    var featureGraphicImg = document.getElementById('rm-app-feature-graphic-img')
    if (featureGraphicImg === null) {
        featureGraphicImg = document.createElement('img')
        featureGraphicImg.id = 'rm-app-feature-graphic-img'
        featureGraphicImg.src = featureGraphicUrl

        var featureGraphicDelete = document.createElement('a')
        featureGraphicDelete.href = Urls.delete_feature_graphic(repo, app)
        featureGraphicDelete.classList.add('rm-app-feature-graphic-delete')

        var featureGraphicDeleteButton = document.createElement('button')
        featureGraphicDeleteButton.type = 'button'
        featureGraphicDeleteButton.classList.add('mdl-js-button')

        var featureGraphicDeleteButtonContent = document.createElement('i')
        featureGraphicDeleteButtonContent.innerText = 'delete'

        featureGraphicDeleteButton.appendChild(featureGraphicDeleteButtonContent)
        featureGraphicDelete.appendChild(featureGraphicDeleteButton)

        featureGraphicContainer.appendChild(featureGraphicImg)
        featureGraphicContainer.appendChild(featureGraphicDelete)
    }
    else {
        featureGraphicImg.src = featureGraphicUrl

        var featureGraphicDelete = featureGraphicContainer.querySelector('.rm-app-feature-graphic-delete')
        featureGraphicDelete.href = Urls.delete_feature_graphic(repo, app)
    }

    resetDndField(dndField)
    registerDeleteListenerFeatureGraphic()
}

function addApks(dndField, response) {
    var apksContainer = dndField.parentElement // TODO getElementById
    var appVersionList = apksContainer.querySelector('.rm-app-versions-list')
    if (appVersionList === null) {
        appVersionList = document.createElement('ul')
        appVersionList.classList.add('rm-app-versions-list')
        appVersionList.classList.add('mdl-list')

        apksContainer.appendChild(appVersionList)

        var apksContainerEmpty = document.getElementById('rm-app-versions-empty')
        apksContainer.removeChild(apksContainerEmpty)
    }
    var repo = response['repo']
    var app = response['app']
    var apks = response['apks']
    for (var i = 0; i < apks.length; i++) {
        var id = apks[i]['id']
        var version = apks[i]['version']
        var released = apks[i]['released']

        var apkLi = document.createElement('li')
        apkLi.classList.add('rm-app-versions-item')

        var apkDelete = document.createElement('a')
        apkDelete.href = Urls.apk_delete(repo, app, id)
        apkDelete.classList.add('rm-app-versions-item-delete')
        apkDelete.dataset.id = id

        var apkDeleteButton = document.createElement('button')
        apkDeleteButton.type = 'button'
        apkDeleteButton.classList.add('mdl-js-button')

        var apkDeleteButtonContent = document.createElement('i')
        apkDeleteButtonContent.innerText = 'delete'

        apkDeleteButton.appendChild(apkDeleteButtonContent)
        apkDelete.appendChild(apkDeleteButton)

        var apkInfo = document.createElement('span')
        apkInfo.classList.add('rm-app-versions-item-info')

        var apkInfoVersion = document.createElement('span')
        apkInfoVersion.innerText = version

        var apkInfoReleased = document.createElement('span')
        apkInfoReleased.classList.add('rm-app-versions-item-info-released')
        apkInfoReleased.innerText = released

        apkInfo.appendChild(apkInfoVersion)
        apkInfo.appendChild(apkInfoReleased)

        apkLi.appendChild(apkInfo)
        apkLi.appendChild(apkDelete)

        appVersionList.insertBefore(apkLi, appVersionList.firstChild)
        registerDeleteListenerApk(apkDelete)
    }
    resetDndField(dndField)
}

function showDndTexts() {
    var elements = document.getElementsByClassName('rm-dng-text')
    for (var i = 0; i < elements.length; i++) {
        elements[i].hidden = false
    }
}

var dndFieldOriginalContent = null

function showError(element, text) {
    element.hidden = false
    document.getElementById(element.id + '--loading').hidden = true
    dndFieldOriginalContent = element.innerHTML
    element.innerHTML = '<p class="error">' + text + '</p>'
    element.innerHTML += '<p>' + gettext('Try to drag and drop again!') + '</p>'
}

function resetDndField(dndField) {
    var loadingField = document.getElementById(dndField.id + '--loading')
    dndField.hidden = false
    loadingField.hidden = true
    if (dndFieldOriginalContent !== null) {
        dndField.innerHTML = dndFieldOriginalContent
    }
}

function isImage(file) {
    return file['type'].split('/')[0] === 'image'
}
