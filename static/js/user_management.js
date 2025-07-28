// User Management JavaScript
// Vanilla JavaScript replacement for Vue.js functionality

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
        phone: '',
        school_id: ''
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
        phone: '',
        school_id: ''
    },
    errors: {
        name: '',
        email: '',
        phone: ''
    },
    isSubmitting: false,
    formAction: ''
};

// Validation Functions
function validateName(formObj, value) {
    if (!value) {
        formObj.errors.name = 'Name is required';
    } else if (value.length < 2) {
        formObj.errors.name = 'Name must be at least 2 characters';
    } else {
        formObj.errors.name = '';
    }
    return formObj.errors.name === '';
}

function validateEmail(formObj, value) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!value) {
        formObj.errors.email = 'Email is required';
    } else if (!emailRegex.test(value)) {
        formObj.errors.email = 'Please enter a valid email address';
    } else {
        formObj.errors.email = '';
    }
    return formObj.errors.email === '';
}

function validatePhone(formObj, value) {
    if (!value) {
        formObj.errors.phone = '';
        return true;
    }

    // Remove all non-digit characters for validation
    const digitsOnly = value.replace(/\D/g, '');

    if (digitsOnly.length !== 10) {
        formObj.errors.phone = 'Phone number must be 10 digits';
        return false;
    } else {
        // Format the phone number as (XXX) XXX-XXXX
        formObj.formData.phone = `(${digitsOnly.substring(0, 3)}) ${digitsOnly.substring(3, 6)}-${digitsOnly.substring(6)}`;
        formObj.errors.phone = '';
        return true;
    }
}

// Form Validation
function isFormValid(formObj) {
    return formObj.formData.name && 
           formObj.formData.email && 
           !formObj.errors.name && 
           !formObj.errors.email && 
           !formObj.errors.phone;
}

// UI Update Functions
function updateValidationUI(formPrefix) {
    const formObj = formPrefix === 'edit-' ? editUserForm : addUserForm;
    
    // Update name field
    const nameInput = document.getElementById(`${formPrefix}name`);
    if (formObj.errors.name) {
        nameInput.classList.add('is-invalid');
        document.getElementById(`${formPrefix}name-error`).textContent = formObj.errors.name;
        document.getElementById(`${formPrefix}name-error`).style.display = 'block';
    } else {
        nameInput.classList.remove('is-invalid');
        document.getElementById(`${formPrefix}name-error`).style.display = 'none';
    }
    
    // Update email field
    const emailInput = document.getElementById(`${formPrefix}email`);
    if (formObj.errors.email) {
        emailInput.classList.add('is-invalid');
        document.getElementById(`${formPrefix}email-error`).textContent = formObj.errors.email;
        document.getElementById(`${formPrefix}email-error`).style.display = 'block';
    } else {
        emailInput.classList.remove('is-invalid');
        document.getElementById(`${formPrefix}email-error`).style.display = 'none';
    }
    
    // Update phone field
    const phoneInput = document.getElementById(`${formPrefix}phone`);
    if (formObj.errors.phone) {
        phoneInput.classList.add('is-invalid');
        document.getElementById(`${formPrefix}phone-error`).textContent = formObj.errors.phone;
        document.getElementById(`${formPrefix}phone-error`).style.display = 'block';
        document.getElementById(`${formPrefix}phone-hint`).style.display = 'none';
    } else {
        phoneInput.classList.remove('is-invalid');
        document.getElementById(`${formPrefix}phone-error`).style.display = 'none';
        
        // Show format hint if phone has value
        if (formObj.formData.phone) {
            document.getElementById(`${formPrefix}phone-hint`).style.display = 'block';
        } else {
            document.getElementById(`${formPrefix}phone-hint`).style.display = 'none';
        }
    }
    
    // Update submit button state
    const submitBtn = document.getElementById(`${formPrefix}submit-btn`);
    submitBtn.disabled = !isFormValid(formObj) || formObj.isSubmitting;
    
    // Update submit button text based on isSubmitting
    const submitBtnText = document.getElementById(`${formPrefix}submit-btn-text`);
    const submitBtnLoader = document.getElementById(`${formPrefix}submit-btn-loader`);
    
    if (formObj.isSubmitting) {
        submitBtnText.style.display = 'none';
        submitBtnLoader.style.display = 'inline-block';
    } else {
        submitBtnText.style.display = 'inline-block';
        submitBtnLoader.style.display = 'none';
    }
}

// Update counters for selected items
function updateCounters(formPrefix) {
    const formObj = formPrefix === 'edit-' ? editUserForm : addUserForm;
    
    // Update grades counter
    const gradesCounter = document.getElementById(`${formPrefix}grades-counter`);
    if (formObj.formData.grades.length > 0) {
        gradesCounter.textContent = `Selected: ${formObj.formData.grades.length} grade(s)`;
        gradesCounter.style.display = 'block';
    } else {
        gradesCounter.style.display = 'none';
    }
    
    // Update subjects counter
    const subjectsCounter = document.getElementById(`${formPrefix}subjects-counter`);
    if (formObj.formData.subjects.length > 0) {
        subjectsCounter.textContent = `Selected: ${formObj.formData.subjects.length} subject(s)`;
        subjectsCounter.style.display = 'block';
    } else {
        subjectsCounter.style.display = 'none';
    }
    
    // Update schools counter
    const schoolsCounter = document.getElementById(`${formPrefix}schools-counter`);
    if (formObj.formData.schools.length > 0) {
        schoolsCounter.textContent = `Selected: ${formObj.formData.schools.length} school(s)`;
        schoolsCounter.style.display = 'block';
    } else {
        schoolsCounter.style.display = 'none';
    }
}

// Form Reset Functions
function resetAddUserForm() {
    addUserForm.formData = {
        name: '',
        email: '',
        role: 'teacher',
        grades: [],
        subjects: [],
        schools: [],
        phone: '',
        school_id: ''
    };
    addUserForm.errors = {
        name: '',
        email: '',
        phone: ''
    };
    addUserForm.isSubmitting = false;
    
    // Reset form fields
    document.getElementById('name').value = '';
    document.getElementById('email').value = '';
    document.getElementById('role').value = 'teacher';
    document.getElementById('phone').value = '';
    
    // Reset checkboxes
    document.querySelectorAll('input[name="grades"]').forEach(checkbox => {
        checkbox.checked = false;
    });
    document.querySelectorAll('input[name="subjects"]').forEach(checkbox => {
        checkbox.checked = false;
    });
    document.querySelectorAll('input[name="schools"]').forEach(checkbox => {
        checkbox.checked = false;
    });
    
    // Update UI
    updateValidationUI('');
    updateCounters('');
}

function resetEditUserForm() {
    editUserForm.formData = {
        userId: '',
        name: '',
        email: '',
        role: 'teacher',
        grades: [],
        subjects: [],
        schools: [],
        phone: '',
        school_id: ''
    };
    editUserForm.errors = {
        name: '',
        email: '',
        phone: ''
    };
    editUserForm.isSubmitting = false;
    editUserForm.formAction = '';
    
    // Reset form fields
    document.getElementById('edit-name').value = '';
    document.getElementById('edit-email').value = '';
    document.getElementById('edit-role').value = 'teacher';
    document.getElementById('edit-phone').value = '';
    document.getElementById('edit-user-id').value = '';
    
    // Reset checkboxes
    document.querySelectorAll('input[name="grades"]').forEach(checkbox => {
        checkbox.checked = false;
    });
    document.querySelectorAll('input[name="subjects"]').forEach(checkbox => {
        checkbox.checked = false;
    });
    document.querySelectorAll('input[name="schools"]').forEach(checkbox => {
        checkbox.checked = false;
    });
    
    // Update UI
    updateValidationUI('edit-');
    updateCounters('edit-');
}

// Set User Data for Edit Form
function setUserData(userData) {
    editUserForm.formData.userId = userData.userId;
    editUserForm.formData.name = userData.name;
    editUserForm.formData.email = userData.email;
    editUserForm.formData.role = userData.role;
    editUserForm.formData.phone = userData.phone || '';
    editUserForm.formData.school_id = userData.school_id || '';
    editUserForm.formData.grades = userData.grades || [];
    editUserForm.formData.subjects = userData.subjects || [];
    editUserForm.formData.schools = userData.schools || [];
    editUserForm.formAction = `/edit_user/${userData.userId}`;
    
    // Set form fields
    document.getElementById('edit-name').value = userData.name;
    document.getElementById('edit-email').value = userData.email;
    document.getElementById('edit-role').value = userData.role;
    document.getElementById('edit-phone').value = userData.phone || '';
    document.getElementById('edit-user-id').value = userData.userId;
    
    // Set form action
    document.getElementById('edit-user-form').action = `/edit_user/${userData.userId}`;
    
    // Set checkboxes
    document.querySelectorAll('input[name="grades"]').forEach(checkbox => {
        checkbox.checked = userData.grades.includes(parseInt(checkbox.value));
    });
    document.querySelectorAll('input[name="subjects"]').forEach(checkbox => {
        checkbox.checked = userData.subjects.includes(parseInt(checkbox.value));
    });
    document.querySelectorAll('input[name="schools"]').forEach(checkbox => {
        checkbox.checked = userData.schools.includes(parseInt(checkbox.value));
    });
    
    // Update UI
    updateValidationUI('edit-');
    updateCounters('edit-');
}

// Form Submission Functions
function submitAddUserForm(event) {
    event.preventDefault();
    
    // Validate all fields
    validateName(addUserForm, addUserForm.formData.name);
    validateEmail(addUserForm, addUserForm.formData.email);
    validatePhone(addUserForm, addUserForm.formData.phone);
    
    // Update UI
    updateValidationUI('');
    
    // Check if form is valid
    if (!isFormValid(addUserForm)) {
        return;
    }
    
    // Set submitting state
    addUserForm.isSubmitting = true;
    updateValidationUI('');
    
    // Submit the form
    document.getElementById('add-user-form').submit();
}

function submitEditUserForm(event) {
    event.preventDefault();
    
    // Validate all fields
    validateName(editUserForm, editUserForm.formData.name);
    validateEmail(editUserForm, editUserForm.formData.email);
    validatePhone(editUserForm, editUserForm.formData.phone);
    
    // Update UI
    updateValidationUI('edit-');
    
    // Check if form is valid
    if (!isFormValid(editUserForm)) {
        return;
    }
    
    // Set submitting state
    editUserForm.isSubmitting = true;
    updateValidationUI('edit-');
    
    // Submit the form
    document.getElementById('edit-user-form').submit();
}

// Initialize Event Listeners
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap modals
    addUserModal = new bootstrap.Modal(document.getElementById('add-user-modal'));
    editUserModal = new bootstrap.Modal(document.getElementById('edit-user-modal'));
    deleteUserModal = new bootstrap.Modal(document.getElementById('delete-user-modal'));

    // Add User Modal
    const addUserBtn = document.getElementById('add-user-btn');
    const addUserForm = document.getElementById('add-user-form');
    const addUserCloseBtn = document.querySelector('#add-user-modal .btn-close');
    const addUserCancelBtn = document.querySelector('#add-user-modal .btn-secondary');
    
    // Add User Form Fields
    const nameInput = document.getElementById('name');
    const emailInput = document.getElementById('email');
    const roleSelect = document.getElementById('role');
    const phoneInput = document.getElementById('phone');
    const gradeCheckboxes = document.querySelectorAll('input[name="grades"]');
    const subjectCheckboxes = document.querySelectorAll('input[name="subjects"]');
    const schoolCheckboxes = document.querySelectorAll('input[name="schools"]');
    
    // Edit User Modal
    const editUserForm = document.getElementById('edit-user-form');
    const editUserCloseBtn = document.querySelector('#edit-user-modal .btn-close');
    const editUserCancelBtn = document.querySelector('#edit-user-modal .btn-secondary');
    
    // Edit User Form Fields
    const editNameInput = document.getElementById('edit-name');
    const editEmailInput = document.getElementById('edit-email');
    const editRoleSelect = document.getElementById('edit-role');
    const editPhoneInput = document.getElementById('edit-phone');
    const editGradeCheckboxes = document.querySelectorAll('#edit-user-modal input[name="grades"]');
    const editSubjectCheckboxes = document.querySelectorAll('#edit-user-modal input[name="subjects"]');
    const editSchoolCheckboxes = document.querySelectorAll('#edit-user-modal input[name="schools"]');
    
    // Delete User Modal
    const deleteButtons = document.querySelectorAll('.delete-btn');
    const deleteUserName = document.getElementById('delete-user-name');
    const deleteUserId = document.getElementById('delete-user-id');
    const deleteUserForm = document.getElementById('delete-user-form');
    
    // Add User Button Click
    addUserBtn.addEventListener('click', () => {
        resetAddUserForm();
        addUserModal.show();
    });
    
    // Add User Form Submit
    addUserForm.addEventListener('submit', submitAddUserForm);
    
    // Add User Form Close/Cancel
    addUserCloseBtn.addEventListener('click', resetAddUserForm);
    addUserCancelBtn.addEventListener('click', resetAddUserForm);
    
    // Add User Form Input Events
    nameInput.addEventListener('input', (e) => {
        addUserForm.formData.name = e.target.value;
        validateName(addUserForm, e.target.value);
        updateValidationUI('');
    });
    
    emailInput.addEventListener('input', (e) => {
        addUserForm.formData.email = e.target.value;
        validateEmail(addUserForm, e.target.value);
        updateValidationUI('');
    });
    
    roleSelect.addEventListener('change', (e) => {
        addUserForm.formData.role = e.target.value;
    });
    
    phoneInput.addEventListener('input', (e) => {
        addUserForm.formData.phone = e.target.value;
        validatePhone(addUserForm, e.target.value);
        updateValidationUI('');
    });
    
    // Add User Form Checkbox Events
    gradeCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                addUserForm.formData.grades.push(parseInt(e.target.value));
            } else {
                addUserForm.formData.grades = addUserForm.formData.grades.filter(id => id !== parseInt(e.target.value));
            }
            updateCounters('');
        });
    });
    
    subjectCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                addUserForm.formData.subjects.push(parseInt(e.target.value));
            } else {
                addUserForm.formData.subjects = addUserForm.formData.subjects.filter(id => id !== parseInt(e.target.value));
            }
            updateCounters('');
        });
    });
    
    schoolCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                addUserForm.formData.schools.push(parseInt(e.target.value));
                // For backward compatibility
                if (addUserForm.formData.schools.length === 1) {
                    addUserForm.formData.school_id = e.target.value;
                }
            } else {
                addUserForm.formData.schools = addUserForm.formData.schools.filter(id => id !== parseInt(e.target.value));
                // For backward compatibility
                if (addUserForm.formData.schools.length === 0) {
                    addUserForm.formData.school_id = '';
                } else {
                    addUserForm.formData.school_id = addUserForm.formData.schools[0].toString();
                }
            }
            updateCounters('');
        });
    });
    
    // Edit User Form Submit
    editUserForm.addEventListener('submit', submitEditUserForm);
    
    // Edit User Form Close/Cancel
    editUserCloseBtn.addEventListener('click', resetEditUserForm);
    editUserCancelBtn.addEventListener('click', resetEditUserForm);
    
    // Edit User Form Input Events
    editNameInput.addEventListener('input', (e) => {
        editUserForm.formData.name = e.target.value;
        validateName(editUserForm, e.target.value);
        updateValidationUI('edit-');
    });
    
    editEmailInput.addEventListener('input', (e) => {
        editUserForm.formData.email = e.target.value;
        validateEmail(editUserForm, e.target.value);
        updateValidationUI('edit-');
    });
    
    editRoleSelect.addEventListener('change', (e) => {
        editUserForm.formData.role = e.target.value;
    });
    
    editPhoneInput.addEventListener('input', (e) => {
        editUserForm.formData.phone = e.target.value;
        validatePhone(editUserForm, e.target.value);
        updateValidationUI('edit-');
    });
    
    // Edit User Form Checkbox Events
    editGradeCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                editUserForm.formData.grades.push(parseInt(e.target.value));
            } else {
                editUserForm.formData.grades = editUserForm.formData.grades.filter(id => id !== parseInt(e.target.value));
            }
            updateCounters('edit-');
        });
    });
    
    editSubjectCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                editUserForm.formData.subjects.push(parseInt(e.target.value));
            } else {
                editUserForm.formData.subjects = editUserForm.formData.subjects.filter(id => id !== parseInt(e.target.value));
            }
            updateCounters('edit-');
        });
    });
    
    editSchoolCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                editUserForm.formData.schools.push(parseInt(e.target.value));
                // For backward compatibility
                if (editUserForm.formData.schools.length === 1) {
                    editUserForm.formData.school_id = e.target.value;
                }
            } else {
                editUserForm.formData.schools = editUserForm.formData.schools.filter(id => id !== parseInt(e.target.value));
                // For backward compatibility
                if (editUserForm.formData.schools.length === 0) {
                    editUserForm.formData.school_id = '';
                } else {
                    editUserForm.formData.school_id = editUserForm.formData.schools[0].toString();
                }
            }
            updateCounters('edit-');
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
            const userSchoolId = button.dataset.userSchoolId;

            // Get the user's grades, subjects, and schools from data attributes
            let userGrades = [];
            let userSubjects = [];
            let userSchools = [];

            try {
                // Parse the JSON data from the data attributes
                userGrades = JSON.parse(button.dataset.userGrades || '[]');
                userSubjects = JSON.parse(button.dataset.userSubjects || '[]');
                
                // For backward compatibility, if schools data attribute exists, use it
                // otherwise create a single-item array with the school_id if it exists
                if (button.dataset.userSchools) {
                    userSchools = JSON.parse(button.dataset.userSchools || '[]');
                } else if (button.dataset.userSchoolId) {
                    userSchools = [parseInt(button.dataset.userSchoolId)];
                }
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
                school_id: userSchoolId || '',
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
});