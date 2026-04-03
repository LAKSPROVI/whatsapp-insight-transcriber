-- redact.lua
-- Fluent Bit Lua filter to redact sensitive data from log records

local SENSITIVE_PARAMS = { "token", "key", "password", "secret" }

local function redact_url_params(url)
    if url == nil then
        return url
    end
    for _, param in ipairs(SENSITIVE_PARAMS) do
        -- Match param=value where value is terminated by & or end of string
        url = url:gsub("([?&])" .. param .. "=[^&]*", "%1" .. param .. "=REDACTED")
    end
    return url
end

function redact_sensitive(tag, timestamp, record)
    local modified = false

    -- Redact sensitive query params from http.url
    if record["http.url"] ~= nil then
        local redacted = redact_url_params(record["http.url"])
        if redacted ~= record["http.url"] then
            record["http.url"] = redacted
            modified = true
        end
    end

    -- Also check nested url field
    if record["url"] ~= nil then
        local redacted = redact_url_params(record["url"])
        if redacted ~= record["url"] then
            record["url"] = redacted
            modified = true
        end
    end

    -- Redact Authorization header
    if record["authorization"] ~= nil then
        record["authorization"] = "REDACTED"
        modified = true
    end
    if record["http.authorization"] ~= nil then
        record["http.authorization"] = "REDACTED"
        modified = true
    end
    if record["Authorization"] ~= nil then
        record["Authorization"] = "REDACTED"
        modified = true
    end

    if modified then
        return 1, timestamp, record
    end

    return 0, timestamp, record
end
