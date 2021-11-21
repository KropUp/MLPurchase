CREATE TABLE public.eis_companies_i (
    inn character varying,
    name character varying
);
CREATE TABLE public.eis_company_attributes_i (
    company_inn character varying,
    attribute_type character varying,
    attribute_value character varying
);
CREATE TABLE public.eis_contracts_i (
    "reestrNumber" character varying,
    purchase character varying,
    price numeric,
    customer character varying,
    executor character varying
);
CREATE TABLE public.eis_purchases_i (
    "regNumber" character varying,
    name character varying,
    max_price numeric,
    currency character varying,
    update_dt date,
    code character varying
);