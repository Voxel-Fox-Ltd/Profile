async function getField(node) {
    while(!node.className.includes("field")) {
        node = node.parentNode;
    }
    return node;
}

async function getFieldSubmitButton(node) {
    node = await getField(node);
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


async function sendUpdateTemplate(node) {
    field = await getField(node);
    data = {
        template_id: field.querySelector('[name=template_id]').value,
        verification_channel_id: field.querySelector('[name=verification_channel_id]').value,
        archive_channel_id: field.querySelector('[name=archive_channel_id]').value,
        role_id: field.querySelector('[name=role_id]').value,
        max_profile_count: field.querySelector('[name=max_profile_count]').value,
    };
    site = await fetch("/api/update_template", {
        method: "POST",
        body: JSON.stringify(data)
    });
    if(site.ok) {
        alert("Updated template.");
        node.disabled = true;
    }
    else {
        body = await site.text()
        alert(`Failed to update template - ${body}.`);
    }
}


async function sendUpdateField(node) {
    field = await getField(node);
    data = {
        field_id: field.querySelector('[name=field_id]').value,
        name: field.querySelector('[name=name]').value,
        prompt: field.querySelector('[name=prompt]').value,
        timeout: field.querySelector('[name=timeout]').value,
        type: field.querySelector('[name=type]').value,
        optional: field.querySelector('[name=optional]').value,
    };
    site = await fetch("/api/update_template_field", {
        method: "POST",
        body: JSON.stringify(data)
    });
    if(site.ok) {
        alert("Updated field.");
        node.disabled = true;
    }
    else {
        body = await site.text()
        alert(`Failed to update field - ${body}.`);
    }
}


window.addEventListener("beforeunload", function (e) {
    shouldPrevent = false;
    for(i of document.getElementsByClassName("submit-button")) {
        if(i.className.includes("delete-button")) continue;
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
