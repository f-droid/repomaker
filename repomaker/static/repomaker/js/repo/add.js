var form = document.querySelector('form')
var spinner = document.querySelector('.mdl-spinner')

form.addEventListener("submit", function() {
    form.querySelector('input[type=submit]').hidden = true
    spinner.hidden = false
})
