async function saveTemplate() {
  const template_id = document.getElementById('template_id').innerText;
  const guild_id = document.getElementById('guild_id').innerText;
  const templateElem = document.getElementById('template-info');
  const templateData = {
    guild_id,
    template_id,
    name: templateElem.querySelector('#name').value,
    verification_channel_id: templateElem.querySelector('#verification_channel_id').value,
    archive_channel_id: templateElem.querySelector('#archive_channel_id').value,
    role_id: templateElem.querySelector('#role_id').value,
    max_profile_count: templateElem.querySelector('#max_profile_count').value
  }
  const res = await fetch('/api/update_template', {
    method: 'POST',
    body: JSON.stringify(templateData)
  });
  if (res.ok) {
    alert('Template saved!');
  } else {
    const { error } = await res.json();
    alert('There was an error saving the template: ' + error);
  }
}

async function deleteTemplate() {
  const template_id = document.getElementById('template_id').innerText;
  if (confirm('Are you REALLY SURE that you want to delete this template?')) {
    const res = await fetch('/api/update_template', {
      method: 'DELETE',
      body: JSON.stringify({ template_id })
    });
    if (res.ok) {
      alert('Template deleted!');
      location.pathname = location.pathname.replace(/\/templates\/[0-9a-f-]+/, '');
    } else {
      const { error } = await res.json();
      alert('There was an error deleting that template: ' + error);
    }
  }
}

async function saveField(field_id) {
  const fieldElem = document.querySelector(`[field-id="${field_id}"]`);
  const fieldData = {
    field_id,
    name: fieldElem.querySelector('#name').value,
    prompt: fieldElem.querySelector('#prompt').value,
    timeout: fieldElem.querySelector('#timeout').value,
    type: fieldElem.querySelector('#type').value,
    optional: fieldElem.querySelector('#optional').value
  };
  const res = await fetch('/api/update_template_field', {
    method: 'POST',
    body: JSON.stringify(fieldData)
  });
  if (res.ok) {
    alert('Field saved!');
  } else {
    const { error } = await res.json();
    alert('There was an error saving the field: ' + error);
  }
}

async function deleteField(field_id) {
  if (confirm('Are you REALLY SURE that you want to delete this field?')) {
    const res = await fetch('/api/update_template_field', {
      method: 'DELETE',
      body: JSON.stringify({ field_id: field_id })
    });
    if (res.ok) {
      alert('Field deleted!');
      document.querySelector(`[field-id="${field_id}"]`).outerHTML = ''; // delete field element
    } else {
      const { error } = await res.json();
      alert('There was an error deleting that field: ' + error);
    }
  }
}

// document.addEventListener('scroll', e => {
//   const position = window.scrollY;
//   const sticky = document.getElementById('template-info');
//   sticky.className = position ? 'minimized' : '';
// });