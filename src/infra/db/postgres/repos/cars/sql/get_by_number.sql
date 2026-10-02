SELECT
    car_id,
    model,
    number,
    current_mileage
FROM cars
WHERE number = :number;