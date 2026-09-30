SELECT
    employee_id,
    username,
    password_hash,
    role,
    is_active,
    created_at
FROM employees
WHERE employee_id = :employee_id;