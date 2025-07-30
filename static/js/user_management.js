// User Management JavaScript
// Completely rebuilt form validation logic

// Initialize Bootstrap modals
let addUserModal, editUserModal, deleteUserModal;

// Add User Form Data and State
const addUserForm = {
    formData: {
        name: '',
        email: '',
        role: 'teacher',
        grades: [],
        subjects: [],
        schools: [],
        phone: ''
    },
    errors: {
        name: '',
        email: '',
        phone: ''
    },
    isSubmitting: false
};

// Edit User Form Data and State
const editUserForm = {
    formData: {
        userId: '',
        name: '',
        email: '',
        role: 'teacher',
        grades: [],
        subjects: [],
        schools: [],
        phone: ''
    },
    errors: {
        name: '',
        email: '',
        phone: ''
    },
    isSubmitting: false
};

// Validation Functions
function validateName(value) {
    if (!value || value.trim() === '') {
        return 'Name is required';
    } else if (value.length < 2) {
        return 'Name must be at least 2 characters';
    }
    return '';
}

function validateEmail(value) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!value || value.trim() === '') {
        return 'Email is required';
    } else if (!emailRegex.test(value)) {
        return 'Please enter a valid email address';
    }
    return '';
}

function validatePhone(value) {
    if (!value || value.trim() === '') {
        return ''; // Phone is optional
    }
    
    // Remove all non-digit characters for validation
    const digitsOnly = value.replace(/\D/g, '');
    
    if (digitsOnly.length !== 10) {
        return 'Phone number must be 10 digits';
    }
    
    return '';
}

function formatPhone(value) {
    if (!value) return '';
    
    // Remove all non-digit characters
    const digitsOnly = value.replace(/\D/g, '');
    
    if (digitsOnly.length === 10) {
        // Format as (XXX) XXX-XXXX
        return `(${digitsOnly.substring(0, 3)}) ${digitsOnly.substring(3, 6)}-${digitsOnly.substring(6)}`;
    }
    
    return value;
}

// Check if all required fields are filled
function checkFormValidity(formPrefix) {
    const form = formPrefix === 'edit-' ? editUserForm : addUserForm;
    
    // Check required fields
    const nameValid = form.formData.name && !form.errors.name;
    const emailValid = form.formData.email && !form.errors.email;
    const phoneValid = !form.errors.phone; // Phone is optional but must be valid if provided
    
    // Enable the submit button if all required fields are valid
    const submitBtn = document.getElementById(`${formPrefix}submit-btn`);
    if (submitBtn) {
        submitBtn.disabled = !(nameValid && emailValid && phoneValid) || form.isSubmitting;
    }
    
    return nameValid && emailValid && phoneValid;
}

// Update form field UI based on validation
function updateFieldUI(fieldId, errorMessage) {
    const field = document.getElementById(fieldId);
    const errorElement = document.getElementById(`${fieldId}-error`);
    
    if (!field || !errorElement) return;
    
    if (errorMessage) {
        field.classList.add('is-invalid');
        errorElement.textContent = errorMessage;
        errorElement.style.display = 'block';
    } else {
        field.classList.remove('is-invalid');
        errorElement.textContent = '';
        errorElement.style.display = 'none';
    }
}

// Update phone hint display
function updatePhoneHint(formPrefix, show) {
    const phoneHint = document.getElementById(`${formPrefix}phone-hint`);
    if (phoneHint) {
        phoneHint.style.display = show ? 'block' : 'none';
    }
}

// Update counters for selected items
function updateCounter(counterId, items) {
    const counter = document.getElementById(counterId);
    if (!counter) return;
    
    if (items && items.length > 0) {
        const itemType = counterId.includes('grades') ? 'grade(s)' : 
                         counterId.includes('subjects') ? 'subject(s)' : 'school(s)';
        counter.textContent = `Selected: ${items.length} ${itemType}`;
        counter.style.display = 'block';
    } else {
        counter.style.display = 'none';
    }
}

// Update submit button state
function updateSubmitButton(formPrefix, isSubmitting) {
    const submitBtn = document.getElementById(`${formPrefix}submit-btn`);
    const submitBtnText = document.getElementById(`${formPrefix}submit-btn-text`);
    const submitBtnLoader = document.getElementById(`${formPrefix}submit-btn-loader`);
    
    if (!submitBtn || !submitBtnText || !submitBtnLoader) return;
    
    if (isSubmitting) {
        submitBtnText.style.display = 'none';
        submitBtnLoader.style.display = 'inline-block';
    } else {
        submitBtnText.style.display = 'inline-block';
        submitBtnLoader.style.display = 'none';
    }
}

// Reset form to initial state
function resetForm(formPrefix) {
    const form = formPrefix === 'edit-' ? editUserForm : addUserForm;
    
    // Reset form data
    form.formData = {
        name: '',
        email: '',
        role: 'teacher',
        grades: [],
        subjects: [],
        schools: [],
        phone: ''
    };
    
    if (formPrefix === 'edit-') {
        form.formData.userId = '';
    }
    
    // Reset errors
    form.errors = {
        name: '',
        email: '',
        phone: ''
    };
    
    form.isSubmitting = false;
    
    // Reset form fields
    const nameInput = document.getElementById(`${formPrefix}name`);
    const emailInput = document.getElementById(`${formPrefix}email`);
    const roleSelect = document.getElementById(`${formPrefix}role`);
    const phoneInput = document.getElementById(`${formPrefix}phone`);
    
    if (nameInput) nameInput.value = '';
    if (emailInput) emailInput.value = '';
    if (roleSelect) roleSelect.value = 'teacher';
    if (phoneInput) phoneInput.value = '';
    
    // Reset user ID for edit form
    if (formPrefix === 'edit-') {
        const userIdInput = document.getElementById('edit-user-id');
        if (userIdInput) userIdInput.value = '';
    }
    
    // Reset checkboxes
    document.querySelectorAll(`${formPrefix === 'edit-' ? '#edit-user-modal ' : ''}input[name="grades"]`).forEach(checkbox => {
        checkbox.checked = false;
    });
    
    document.querySelectorAll(`${formPrefix === 'edit-' ? '#edit-user-modal ' : ''}input[name="subjects"]`).forEach(checkbox => {
        checkbox.checked = false;
    });
    
    document.querySelectorAll(`${formPrefix === 'edit-' ? '#edit-user-modal ' : ''}input[name="schools"]`).forEach(checkbox => {
        checkbox.checked = false;
    });
    
    // Reset UI
    updateFieldUI(`${formPrefix}name`, '');
    updateFieldUI(`${formPrefix}email`, '');
    updateFieldUI(`${formPrefix}phone`, '');
    updatePhoneHint(formPrefix, false);
    updateCounter(`${formPrefix}grades-counter`, []);
    updateCounter(`${formPrefix}subjects-counter`, []);
    updateCounter(`${formPrefix}schools-counter`, []);
    updateSubmitButton(formPrefix, false);
    
    // Disable submit button initially
    const submitBtn = document.getElementById(`${formPrefix}submit-btn`);
    if (submitBtn) submitBtn.disabled = true;
}

// Set user data for edit form
function setUserData(userData) {
    // Set form data
    editUserForm.formData = {
        userId: userData.userId,
        name: userData.name || '',
        email: userData.email || '',
        role: userData.role || 'teacher',
        grades: userData.grades || [],
        subjects: userData.subjects || [],
        schools: userData.schools || [],
        phone: userData.phone || ''
    };
    
    // Reset errors
    editUserForm.errors = {
        name: '',
        email: '',
        phone: ''
    };
    
    // Set form fields
    const nameInput = document.getElementById('edit-name');
    const emailInput = document.getElementById('edit-email');
    const roleSelect = document.getElementById('edit-role');
    const phoneInput = document.getElementById('edit-phone');
    const userIdInput = document.getElementById('edit-user-id');
    
    if (nameInput) nameInput.value = userData.name || '';
    if (emailInput) emailInput.value = userData.email || '';
    if (roleSelect) roleSelect.value = userData.role || 'teacher';
    if (phoneInput) phoneInput.value = userData.phone || '';
    if (userIdInput) userIdInput.value = userData.userId || '';
    
    // Set form action
    const form = document.getElementById('edit-user-form');
    if (form) form.action = `/edit_user/${userData.userId}`;
    
    // Set checkboxes
    document.querySelectorAll('#edit-user-modal input[name="grades"]').forEach(checkbox => {
        checkbox.checked = (userData.grades || []).includes(parseInt(checkbox.value));
    });
    
    document.querySelectorAll('#edit-user-modal input[name="subjects"]').forEach(checkbox => {
        checkbox.checked = (userData.subjects || []).includes(parseInt(checkbox.value));
    });
    
    document.querySelectorAll('#edit-user-modal input[name="schools"]').forEach(checkbox => {
        checkbox.checked = (userData.schools || []).includes(parseInt(checkbox.value));
    });
    
    // Update UI
    updateFieldUI('edit-name', '');
    updateFieldUI('edit-email', '');
    updateFieldUI('edit-phone', '');
    updatePhoneHint('edit-', !!userData.phone);
    updateCounter('edit-grades-counter', userData.grades);
    updateCounter('edit-subjects-counter', userData.subjects);
    updateCounter('edit-schools-counter', userData.schools);
    
    // Check form validity
    checkFormValidity('edit-');
}

// Handle form submission
function submitForm(event, formPrefix) {
    event.preventDefault();
    
    const form = formPrefix === 'edit-' ? editUserForm : addUserForm;
    
    // Validate all fields
    form.errors.name = validateName(form.formData.name);
    form.errors.email = validateEmail(form.formData.email);
    form.errors.phone = validatePhone(form.formData.phone);
    
    // Update UI with validation results
    updateFieldUI(`${formPrefix}name`, form.errors.name);
    updateFieldUI(`${formPrefix}email`, form.errors.email);
    updateFieldUI(`${formPrefix}phone`, form.errors.phone);
    
    // Check if form is valid
    if (!checkFormValidity(formPrefix)) {
        return;
    }
    
    // Set submitting state
    form.isSubmitting = true;
    updateSubmitButton(formPrefix, true);
    
    // Submit the form
    const formId = formPrefix === 'edit-' ? 'edit-user-form' : 'add-user-form';
    document.getElementById(formId).submit();
}

// Initialize event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap modals
    addUserModal = new bootstrap.Modal(document.getElementById('add-user-modal'));
    editUserModal = new bootstrap.Modal(document.getElementById('edit-user-modal'));
    deleteUserModal = new bootstrap.Modal(document.getElementById('delete-user-modal'));
    
    // Add User Modal
    const addUserBtn = document.getElementById('add-user-btn');
    const addUserFormElement = document.getElementById('add-user-form');
    const addUserCloseBtn = document.querySelector('#add-user-modal .btn-close');
    const addUserCancelBtn = document.querySelector('#add-user-modal .btn-secondary');
    
    // Add User Form Fields
    const nameInput = document.getElementById('name');
    const emailInput = document.getElementById('email');
    const roleSelect = document.getElementById('role');
    const phoneInput = document.getElementById('phone');
    
    // Edit User Modal
    const editUserFormElement = document.getElementById('edit-user-form');
    const editUserCloseBtn = document.querySelector('#edit-user-modal .btn-close');
    const editUserCancelBtn = document.querySelector('#edit-user-modal .btn-secondary');
    
    // Edit User Form Fields
    const editNameInput = document.getElementById('edit-name');
    const editEmailInput = document.getElementById('edit-email');
    const editRoleSelect = document.getElementById('edit-role');
    const editPhoneInput = document.getElementById('edit-phone');
    
    // Delete User Modal
    const deleteButtons = document.querySelectorAll('.delete-btn');
    const deleteUserName = document.getElementById('delete-user-name');
    const deleteUserId = document.getElementById('delete-user-id');
    const deleteUserForm = document.getElementById('delete-user-form');
    
    // Add User Button Click
    if (addUserBtn) {
        addUserBtn.addEventListener('click', () => {
            resetForm('');
            addUserModal.show();
        });
    }
    
    // Add User Form Submit
    if (addUserFormElement) {
        addUserFormElement.addEventListener('submit', (event) => submitForm(event, ''));
    }
    
    // Add User Form Close/Cancel
    if (addUserCloseBtn) addUserCloseBtn.addEventListener('click', () => resetForm(''));
    if (addUserCancelBtn) addUserCancelBtn.addEventListener('click', () => resetForm(''));
    
    // Add User Form Input Events
    if (nameInput) {
        nameInput.addEventListener('input', (e) => {
            addUserForm.formData.name = e.target.value;
            addUserForm.errors.name = validateName(e.target.value);
            updateFieldUI('name', addUserForm.errors.name);
            checkFormValidity('');
        });
    }
    
    if (emailInput) {
        emailInput.addEventListener('input', (e) => {
            addUserForm.formData.email = e.target.value;
            addUserForm.errors.email = validateEmail(e.target.value);
            updateFieldUI('email', addUserForm.errors.email);
            checkFormValidity('');
        });
    }
    
    if (roleSelect) {
        roleSelect.addEventListener('change', (e) => {
            addUserForm.formData.role = e.target.value;
        });
    }
    
    if (phoneInput) {
        phoneInput.addEventListener('input', (e) => {
            addUserForm.formData.phone = e.target.value;
            addUserForm.errors.phone = validatePhone(e.target.value);
            updateFieldUI('phone', addUserForm.errors.phone);
            
            // Format phone number if valid
            if (!addUserForm.errors.phone && e.target.value) {
                const formattedPhone = formatPhone(e.target.value);
                if (formattedPhone !== e.target.value) {
                    e.target.value = formattedPhone;
                    addUserForm.formData.phone = formattedPhone;
                }
            }
            
            updatePhoneHint('', !!e.target.value);
            checkFormValidity('');
        });
    }
    
    // Add User Form Checkbox Events
    document.querySelectorAll('input[name="grades"]').forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                addUserForm.formData.grades.push(parseInt(e.target.value));
            } else {
                addUserForm.formData.grades = addUserForm.formData.grades.filter(id => id !== parseInt(e.target.value));
            }
            updateCounter('grades-counter', addUserForm.formData.grades);
            checkFormValidity('');
        });
    });
    
    document.querySelectorAll('input[name="subjects"]').forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                addUserForm.formData.subjects.push(parseInt(e.target.value));
            } else {
                addUserForm.formData.subjects = addUserForm.formData.subjects.filter(id => id !== parseInt(e.target.value));
            }
            updateCounter('subjects-counter', addUserForm.formData.subjects);
            checkFormValidity('');
        });
    });
    
    document.querySelectorAll('input[name="schools"]').forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                addUserForm.formData.schools.push(parseInt(e.target.value));
                
                // For backward compatibility
                document.getElementById('school_id').value = e.target.value;
            } else {
                addUserForm.formData.schools = addUserForm.formData.schools.filter(id => id !== parseInt(e.target.value));
                
                // For backward compatibility
                if (addUserForm.formData.schools.length === 0) {
                    document.getElementById('school_id').value = '';
                } else {
                    document.getElementById('school_id').value = addUserForm.formData.schools[0].toString();
                }
            }
            updateCounter('schools-counter', addUserForm.formData.schools);
            checkFormValidity('');
        });
    });
    
    // Edit User Form Submit
    if (editUserFormElement) {
        editUserFormElement.addEventListener('submit', (event) => submitForm(event, 'edit-'));
    }
    
    // Edit User Form Close/Cancel
    if (editUserCloseBtn) editUserCloseBtn.addEventListener('click', () => resetForm('edit-'));
    if (editUserCancelBtn) editUserCancelBtn.addEventListener('click', () => resetForm('edit-'));
    
    // Edit User Form Input Events
    if (editNameInput) {
        editNameInput.addEventListener('input', (e) => {
            editUserForm.formData.name = e.target.value;
            editUserForm.errors.name = validateName(e.target.value);
            updateFieldUI('edit-name', editUserForm.errors.name);
            checkFormValidity('edit-');
        });
    }
    
    if (editEmailInput) {
        editEmailInput.addEventListener('input', (e) => {
            editUserForm.formData.email = e.target.value;
            editUserForm.errors.email = validateEmail(e.target.value);
            updateFieldUI('edit-email', editUserForm.errors.email);
            checkFormValidity('edit-');
        });
    }
    
    if (editRoleSelect) {
        editRoleSelect.addEventListener('change', (e) => {
            editUserForm.formData.role = e.target.value;
        });
    }
    
    if (editPhoneInput) {
        editPhoneInput.addEventListener('input', (e) => {
            editUserForm.formData.phone = e.target.value;
            editUserForm.errors.phone = validatePhone(e.target.value);
            updateFieldUI('edit-phone', editUserForm.errors.phone);
            
            // Format phone number if valid
            if (!editUserForm.errors.phone && e.target.value) {
                const formattedPhone = formatPhone(e.target.value);
                if (formattedPhone !== e.target.value) {
                    e.target.value = formattedPhone;
                    editUserForm.formData.phone = formattedPhone;
                }
            }
            
            updatePhoneHint('edit-', !!e.target.value);
            checkFormValidity('edit-');
        });
    }
    
    // Edit User Form Checkbox Events
    document.querySelectorAll('#edit-user-modal input[name="grades"]').forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                editUserForm.formData.grades.push(parseInt(e.target.value));
            } else {
                editUserForm.formData.grades = editUserForm.formData.grades.filter(id => id !== parseInt(e.target.value));
            }
            updateCounter('edit-grades-counter', editUserForm.formData.grades);
            checkFormValidity('edit-');
        });
    });
    
    document.querySelectorAll('#edit-user-modal input[name="subjects"]').forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                editUserForm.formData.subjects.push(parseInt(e.target.value));
            } else {
                editUserForm.formData.subjects = editUserForm.formData.subjects.filter(id => id !== parseInt(e.target.value));
            }
            updateCounter('edit-subjects-counter', editUserForm.formData.subjects);
            checkFormValidity('edit-');
        });
    });
    
    document.querySelectorAll('#edit-user-modal input[name="schools"]').forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                editUserForm.formData.schools.push(parseInt(e.target.value));
                
                // For backward compatibility
                document.getElementById('edit-school_id').value = e.target.value;
            } else {
                editUserForm.formData.schools = editUserForm.formData.schools.filter(id => id !== parseInt(e.target.value));
                
                // For backward compatibility
                if (editUserForm.formData.schools.length === 0) {
                    document.getElementById('edit-school_id').value = '';
                } else {
                    document.getElementById('edit-school_id').value = editUserForm.formData.schools[0].toString();
                }
            }
            updateCounter('edit-schools-counter', editUserForm.formData.schools);
            checkFormValidity('edit-');
        });
    });
    
    // Edit User Buttons
    const editButtons = document.querySelectorAll('.edit-btn');
    
    editButtons.forEach(button => {
        button.addEventListener('click', () => {
            const userId = button.dataset.userId;
            const userName = button.dataset.userName;
            const userEmail = button.dataset.userEmail;
            const userRole = button.dataset.userRole;
            const userPhone = button.dataset.userPhone;
            
            // Get the user's grades, subjects, and schools from data attributes
            let userGrades = [];
            let userSubjects = [];
            let userSchools = [];
            
            try {
                // Parse the JSON data from the data attributes
                userGrades = JSON.parse(button.dataset.userGrades || '[]');
                userSubjects = JSON.parse(button.dataset.userSubjects || '[]');
                userSchools = JSON.parse(button.dataset.userSchools || '[]');
            } catch (e) {
                console.error('Error parsing grades, subjects, or schools:', e);
            }
            
            // Set the user data
            setUserData({
                userId: userId,
                name: userName,
                email: userEmail,
                role: userRole,
                phone: userPhone || '',
                grades: userGrades,
                subjects: userSubjects,
                schools: userSchools
            });
            
            // Show the modal
            editUserModal.show();
        });
    });
    
    // Delete User Buttons
    deleteButtons.forEach(button => {
        button.addEventListener('click', () => {
            const userId = button.dataset.userId;
            const userName = button.dataset.userName;
            
            // Populate modal with user details
            deleteUserId.value = userId;
            deleteUserName.textContent = userName;
            
            // Dynamically set the form action
            deleteUserForm.action = `/delete_user/${userId}`;
            
            // Show the modal
            deleteUserModal.show();
        });
    });
    
    // Initialize form state
    resetForm('');
    
    // Check if we need to pre-populate the edit form (e.g., if opened directly)
    const editUserId = document.getElementById('edit-user-id');
    if (editUserId && editUserId.value) {
        checkFormValidity('edit-');
    }
});