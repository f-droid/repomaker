/**
 * Search
 */
var rmRepoAppsHeaderSearch = document.getElementById('id_search')
var rmRepoAppsHeaderSearchInput = document.getElementById('rm-repo-apps-header-search-input')
if (rmRepoAppsHeaderSearch !== null && rmRepoAppsHeaderSearch.value == '') {
    rmRepoAppsHeaderSearchInput.style.display = 'none'
}
function toggleSearch() {
    if (rmRepoAppsHeaderSearchInput.style.display == 'none') {
        rmRepoAppsHeaderSearchInput.style.display = 'block'
        return;
    }
    rmRepoAppsHeaderSearchInput.style.display = 'none'
}

/**
 * Upload files
 */
form = document.querySelector('.rm-repo-apps-add form')
if (form !== null) {
    // Hide add button
    form.querySelector('button[type=submit]').hidden = true
}

/**
 * Pagination
 */
var mdlBody = document.querySelector('.mdl-layout__content')
mdlBody.addEventListener("scroll", function () {
    if (!document.getElementById('rm-repo-panel-apps').classList.contains('is-active')) {
        return
    }
    if (mdlBody.scrollHeight - window.innerHeight -
            mdlBody.scrollTop <= 800) {
        var pagination = document.querySelector('.rm-pagination')
        if (pagination !== null) {
            handlePagination(jsonHtmlRelation, '.rm-repo-apps')
        }
    }
}, false)

document.addEventListener('mdl-componentupgraded', function () {
    var pagination = document.querySelector('.rm-pagination')
    // Check if pagination is already visible at first page load
    if (pagination !== null && isVisible(pagination)) {
        handlePagination(jsonHtmlRelation, '.rm-repo-apps')
    }
})

var jsonHtmlRelation = {
    'rm-app-card-description': 'description',
    'rm-app-card-left': 'icon',
    'rm-app-card-summary': 'summary',
    'rm-app-card-title': 'name',
    'rm-app-card-updated': 'updated',
    'rm-app-card--repo-apps': 'id',
}
