/**
 * Remote App Add
 */

var showScreenshotsButtonContainer = document.querySelector('.rm-remote-app-privacy-button-container')
if (showScreenshotsButtonContainer !== null) {
    var showScreenshotsAnchor = showScreenshotsButtonContainer.querySelector('a')
    showScreenshotsAnchor.addEventListener('click', function (event) {
        event.preventDefault()

        var screenshotsContainer = document.querySelector('.rm-app-screenshots')

        // Screenshot URLs are stored in a datalist element
        var screenshotsData = document.getElementById('rm-app-screenshots-data').options
        for (var i = 0; i < screenshotsData.length; i++) {
            addScreenshot(screenshotsContainer, screenshotsData[i].value)
        }

        // Hide privacy text and button
        var showScreenshotsText = document.querySelector('.rm-remote-app-privacy-text')
        showScreenshotsText.hidden = true
        showScreenshotsButtonContainer.hidden = true

        // Show screenshots
        screenshotsContainer.hidden = false
    })
}

function addScreenshot(screenshotsContainer, url) {
    var container = document.createElement('div')
    container.classList.add('rm-app-screenshot')

    var image = document.createElement('img')
    image.src = url

    container.appendChild(image)
    screenshotsContainer.append(container)
}
