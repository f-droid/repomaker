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
var forms = [
    document.querySelector('.rm-repo-apps-add-locally form'),
    document.querySelector('.rm-repo-apps-empty-add form'),
]
forms.forEach(function(form) {
    if (form !== null) {
        // Hide add button
        form.querySelector('button[type=submit]').hidden = true
        // Submit on end of file selection
        form.querySelector('input[type=file]').onchange = function() {
            this.form.submit()
        }
    }
})
