/**
 * Gets the field object from the HTML by reccursively extending upwards.
 * @param {Node} node The node that you want to extend upwards from.
 * @return {Node} The field object.
 */
async function getField(node) {
    while(!node.className.split(" ").includes("field")) {
        node = node.parentNode;
    }
    return node;
}


/**
 * Find the submit button for a given field node.
 * @param {Node} node The field node that you want to get the submit button for.
 * @return {Node} The submit button for that given field.
 */
async function getFieldSubmitButton(node) {
    node = await getField(node);
    return node.getElementsByClassName("field-submit-button")[0];
}


/**
 * Enable the submit button for a given field.
 * @param {Node} The field node that you want to enable the submit button for.
 */
async function enableFieldSubmitButton(node) {
    b = await getFieldSubmitButton(node);
    b.disabled = false;
}


/**
 * Disable the submit button for a given field.
 * @param {Node} The field node that you want to disable the submit button for.
 */
async function disableFieldSubmitButton(node) {
    b = await getFieldSubmitButton(node);
    b.disabled = true;
}


/**
 * Sends the POST request that updates the template information.
 * @param {Node} The template node that you want to send an update for.
 */
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


/**
 * Sends the DELETE request that removes the template.
 * @param {string} The ID of the template that you want to send a DELETE request for.
 */
async function sendDeleteTemplate(templateId) {
    site = await fetch("/api/update_template", {
        method: "DELETE",
        body: JSON.stringify({template_id: templateId})
    });
    if(site.ok) {
        alert("Deleted template.");
        location.href = document.getElementById("guild-base-url").href;
    }
    else {
        body = await site.text()
        alert(`Failed to delete template - ${body}.`);
    }
}


async function sendUpdateField(node) {
    field = await getField(node);
    data = {
        template_id: field.querySelector('[name=template_id]').value,
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
    if(!site.ok) {
        body = await site.text()
        alert(`Failed to update field - ${body}.`);
        return;
    }
    alert("Updated field.");
    node.disabled = true;
    response = await site.json();

    // Update current fields
    field.querySelector('[name=index]').innerHTML = `Field Index #${response.data.index}`;
    field.querySelector('[name=field_id]').value = response.data.field_id;
    field.querySelector('[name=name]').value = response.data.name;
    field.querySelector('[name=prompt]').value = response.data.prompt;
    field.querySelector('[name=timeout]').value = response.data.timeout;
    field.querySelector('[name=type]').value = response.data.type;
    field.querySelector('[name=optional]').value = response.data.optional;

}


async function sendDeleteField(node) {
    field = await getField(node);
    fieldId = field.querySelector('[name=field_id]').value;
    if(fieldId) {
        let site = await fetch("/api/update_template_field", {
            method: "DELETE",
            body: JSON.stringify({field_id: fieldId})
        });
        if(!site.ok) {
            body = await site.text()
            alert(`Failed to delete field - ${body}.`);
            return;
        }
    }
    alert("Deleted field.");
    hr = field.nextSibling;
    while(hr.tagName != "HR") {
        hr = hr.nextSibling;
    }
    field.parentNode.removeChild(field);
    console.log(hr);
    hr.parentNode.removeChild(hr);
}


async function createField(node) {
    fieldList = document.getElementsByClassName("fields");
    fields = fieldList[fieldList.length - 1]
    baseField = document.getElementById("base-field");
    copyField = baseField.cloneNode(true);

    copyField.id = null;
    fields.appendChild(copyField)
    fields.appendChild(document.createElement("HR"));
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
