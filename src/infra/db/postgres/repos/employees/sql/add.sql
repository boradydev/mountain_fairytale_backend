INSERT INTO employees (
    employee_id,
    username,
    password_hash,
    role,
    is_active,
    created_at
)
VALUES (
    :employee_id,
    :username,
    :password_hash,
    :role,
    :is_active,
    :created_at
);