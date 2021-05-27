async function getFieldSubmitButton(node) {
    while(!node.className.includes("field")) {
        node = node.parentNode;
    }
    return node.getElementsByClassName("submit-button")[0];
}


async function enableFieldSubmitButton(node) {
    b = await getFieldSubmitButton(node);
    b.disabled = false;
}


async function disableFieldSubmitButton(node) {
    b = await getFieldSubmitButton(node);
    b.disabled = true;
}


window.addEventListener("beforeunload", function (e) {
    shouldPrevent = false;
    for(i of document.getElementsByClassName("submit-button")) {
        if(!i.disabled) {
            shouldPrevent = true;
            break;
        }
    }
    if(shouldPrevent){
        e.preventDefault();
        e.returnValue = "";
    }
    else {
        delete e['returnValue'];
    }
});
