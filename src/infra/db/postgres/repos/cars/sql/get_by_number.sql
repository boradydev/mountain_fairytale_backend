SELECT
    car_id,
    model,
    number,
    current_mileage,
    is_active
FROM cars
WHERE number = :number;
