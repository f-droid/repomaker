var button = document.getElementsByClassName('rm-repo-share-share-copy')[0];
if (button !== undefined) {
    button.style.display = 'inline-block';
}
function copyLink(link) {
    var textArea = document.createElement("textarea");
    textArea.value = link;
    document.body.appendChild(textArea);
    textArea.select();

    try {
        var successful = document.execCommand('copy');
        var msg = successful ? 'successful' : 'unsuccessful';
        console.log('Copying link command was ' + msg);
        buttonSetSuccessful();
    } catch (err) {
        console.log('Copying link command was ' + msg + ': ' + err);
    }
}

function buttonSetSuccessful() {
    button.className = 'rm-repo-share-share-copy--successful'
    button.innerHTML = '<i class="material-icons">done</i>'
}
