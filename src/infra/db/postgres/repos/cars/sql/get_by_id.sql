SELECT
    car_id,
    model,
    number,
    current_mileage
FROM cars
WHERE car_id = :car_id;