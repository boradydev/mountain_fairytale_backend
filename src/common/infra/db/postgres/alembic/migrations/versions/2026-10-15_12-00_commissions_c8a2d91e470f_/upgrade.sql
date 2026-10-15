CREATE TABLE point_commissions (
    point_id UUID PRIMARY KEY REFERENCES points(point_id) ON DELETE CASCADE,
    sales_representative_id UUID NULL REFERENCES sales_representatives(sales_representative_id),
    commission_percent NUMERIC NOT NULL CHECK (commission_percent BETWEEN 0 AND 100),
    turnover NUMERIC NOT NULL CHECK (turnover >= 0),
    commission_payable NUMERIC NOT NULL CHECK (commission_payable >= 0)
);
CREATE INDEX ix_point_commissions_sales_representative_id ON point_commissions(sales_representative_id);

CREATE TABLE document_employee_commissions (
    delivery_document_id UUID NOT NULL REFERENCES delivery_documents(delivery_document_id) ON DELETE CASCADE,
    employee_id UUID NOT NULL REFERENCES employees(employee_id),
    commission_percent NUMERIC NOT NULL CHECK (commission_percent BETWEEN 0 AND 100),
    turnover NUMERIC NOT NULL CHECK (turnover >= 0),
    commission_payable NUMERIC NOT NULL CHECK (commission_payable >= 0),
    PRIMARY KEY (delivery_document_id, employee_id)
);
