// Source: http://html5demos.com/dnd-upload
var holders = [
    document.getElementById('rm-dnd-holder--screenshots'),
    document.getElementById('rm-dnd-holder--apks'),
    document.getElementById('rm-dnd-holder-2--apks'),
]

function uploadFiles(element, files) {
    var type = element.id.split("--").pop()
    var formData = new FormData()
    for (var i = 0; i < files.length; i++) {
        if (type == 'screenshots' && !isImage(files[i])) {
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
            holder.ondragover =  function () {
                return onDragOver(this)
            }
            holder.ondragleave = function () {
                return onDragLeave(this)
            }
            holder.ondrop = function (event) {
                return onDrop(this, event)
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
    if (request.status === 204) {
        location.reload()
    }
    else {
        showError(element, request.responseText)
    }
}

function showDndTexts() {
    var elements = document.getElementsByClassName('rm-dng-text')
    for (var i = 0; i < elements.length; i++) {
        elements[i].hidden = false
    }
}

function showError(element, text) {
    element.hidden = false
    document.getElementById(element.id + '--loading').hidden = true
    element.innerHTML = '<p class="error">' + text + '</p>'
    element.innerHTML += '<p>' + gettext('Try to drag and drop again!') + '</p>'
}

function isImage(file) {
    return file['type'].split('/')[0] === 'image'
}
