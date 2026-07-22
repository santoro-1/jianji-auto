local exports = exports or {}
local TextAnim = TextAnim or {}
TextAnim.__index = TextAnim
function TextAnim.new(construct, ...)
    local self = setmetatable({}, TextAnim)
    self.sharedMaterial = nil
    self.materials = nil
    self.renderer = nil
    self.first = true
    self.cached_chars = {}
    if construct and TextAnim.constructor then
        TextAnim.constructor(self, ...)
    end
    return self
end

function TextAnim:constructor()
end

function TextAnim:resetChars()
    if self.text.chars:size() ~= #self.cached_chars then
        return
    end
    for i = 0, self.text.chars:size() - 1 do
        local c_cached = self.cached_chars[i + 1]
        local c = self.text.chars:get(i)
        c.position = c_cached.position:copy()
        c.rotate   = c_cached.rotate:copy()
        c.scale    = c_cached.scale:copy()
        c.color    = c_cached.color:copy()
        self.text.chars:set(i, c)
    end
end

function TextAnim:onStart(comp)
    -- print("zglog TextAnim onStart")
    self.properties = comp.properties
    self.text = comp.entity:getComponent("SDFText")
    self.renderer = comp.entity:getComponent("MeshRenderer")
    self.first = true

    local str = self.text.str
    self.text.str = ""
    self.text.str = str
    self.text:forceTypeSetting()

    for i = 0, self.text.chars:size() - 1 do
        local c = self.text.chars:get(i)
        table.insert(
            self.cached_chars,
            {
                utf8code = c.utf8code,
                position = c.position:copy(),
                rotate   = c.rotate:copy(),
                scale    = c.scale:copy(),
                color    = c.color:copy(),
            }
        )
    end

    self:setCustomRules()
end

function TextAnim:initAnim()
    self.text.renderToRT = true
    local materials = Amaz.Vector()
    materials:pushBack(self.sharedMaterial)
    self.renderer.sharedMaterials = materials
    self.materials = self.renderer.materials
end

function TextAnim:seek(time)
    -- print("zglog TextAnim seek")
    if self.first then
        self:initAnim()
        self.first = false
    end

    self.text.renderToRT = true
    self.renderer.materials = self.materials

    self:setCustomRules()
end

function TextAnim:setDuration(duration)
    self.duration = duration
end

function TextAnim:clear()
    -- print("clear")
    self.renderer.sharedMaterials = Amaz.Vector()
    self.text.renderToRT = false
end

------------------------------------------------------------------

function TextAnim:updateTargetSize()
    local rect = self.text.rect
    local cx = rect.x + 0.5 * rect.width
    local cy = rect.y + 0.5 * rect.height
    -- print('tqh rect0', tostring(rect))
    local x_min = rect.x
    local y_min = rect.y
    local x_max = rect.x + rect.width
    local y_max = rect.y + rect.height
    for i = 0, self.text.chars:size() - 1 do
        local c = self.text.chars:get(i)
        -- print('tqh rect', c.utf8code, tostring(c.position), c.width, c.height)
        local x = c.position.x + cx
        local y = c.position.y + cy
        local halfW = 0.5 * c.scale.x * c.width
        local halfH = 0.5 * c.scale.y * c.height
        x_min = math.min(x - halfW, x_min)
        x_max = math.max(x + halfW, x_max)
        y_min = math.min(y - halfH, y_min)
        y_max = math.max(y + halfH, y_max)
    end
    rect.width  = math.max(cx - x_min, x_max - cx) * 2.0
    rect.height = math.max(cy - y_min, y_max - cy) * 2.0
    rect.x = cx - 0.5 * rect.width
    rect.y = cy - 0.5 * rect.height
    -- print('tqh rect1', tostring(rect))
    local extraW = math.max(self.text.targetRTExtraSize.x, rect.width  + 1.0)
    local extraH = math.max(self.text.targetRTExtraSize.y, rect.height + 1.0)
    self.text.targetRTExtraSize = Amaz.Vector2f(extraW, extraH)
end

function TextAnim:setCustomRules()
    self:resetChars()
    self:curve()
    self:trsc()
    self:updateTargetSize()
    local chars = self.text.chars
    self.text.chars = chars
end

------------------------------------------------------------------

local Bezier = {}
function Bezier:init(P0, P1, P2)
    self.P0 = P0
    self.P1 = P1
    self.P2 = P2
    local ax = P0.x - 2 * P1.x + P2.x
    local ay = P0.y - 2 * P1.y + P2.y
    local bx = 2 * P1.x - 2 * P0.x
    local by = 2 * P1.y - 2 * P0.y
    self.A = 4 * (ax * ax + ay * ay)
    self.B = 4 * (ax * bx + ay * by)
    self.C = bx * bx + by * by
end

function Bezier:L(t)
    local temp1 = math.sqrt(self.C + t * (self.B + self.A * t))
    local temp2 = (2 * self.A * t * temp1 + self.B * (temp1 - math.sqrt(self.C)))
    local temp3 = math.log(self.B + 2 * math.sqrt(self.A) * math.sqrt(self.C))
    local temp4 = math.log(self.B + 2 * self.A * t + 2 * math.sqrt(self.A) * temp1)
    local temp5 = 2 * math.sqrt(self.A) * temp2
    local temp6 = (self.B * self.B - 4 * self.A * self.C) * (temp3 - temp4)
    return (temp5 + temp6) / (8 * math.pow(self.A, 1.5))
end

function Bezier:_s(t)
    return math.sqrt(self.A * t * t + self.B * t + self.C)
end

function Bezier:InvertL(t, l)
    local t1 = t
    local t2 = t
    while (true) do
        t2 = t1 - (self:L(t1) - l) / self:_s(t1)
        if math.abs(t1 - t2) < 0.001 then
            break
        end
        t1 = t2
    end
    return t2
end

function Bezier:point(t)
    local tmp1 = self.P0 + (self.P1 - self.P0) * t
    local tmp2 = self.P1 + (self.P2 - self.P1) * t
    local tangent = (tmp2 - tmp1)
    return tmp1 + tangent * t, tangent
end

function TextAnim:curve()
    local r = self.text.rect
    -- print("zglog rect = " .. r.x .. " " .. r.y .. " " .. r.width .. " " .. r.height)

    local control_X = 0
    local control_Y = 0
    local custom_rule = self.properties:get("custom_rules")
    if custom_rule then
        local curve = custom_rule:get("curve")
        if curve then
            control_X = curve:get("control_X") or 0
            control_Y = curve:get("control_Y") or 0
        end
    end
    -- print("zglog control = " .. control_X .. " " .. control_Y)

    if math.abs(control_Y) < 0.01 then
        return
    end
    if self.text.chars:size() ~= 0 then
        for i = 0, self.text.chars:size() - 1 do
            local c = self.text.chars:get(i)
            local p = c.position

            local P0 = Amaz.Vector2f(r.x, p.y)
            local P1 = Amaz.Vector2f(r.width * control_X, r.width * control_Y + p.y)
            local P2 = Amaz.Vector2f(r.x + r.width, p.y)
            Bezier:init(P0, P1, P2)
            local t = (p.x - r.x) / r.width
            t = Bezier:InvertL(t, Bezier:L(1) * t)
            local new_p, tangent = Bezier:point(t)

            p.x = new_p.x
            p.y = new_p.y
            c.position = p
            -- print("zglog new_p = " .. new_p.x .. " " .. new_p.y)
            local aaa = math.atan(tangent.y / tangent.x)
            c.rotate = Amaz.Vector3f(0.0, 0.0, aaa * 180 / 3.1415926) + c.rotate
            -- print("zglog rotate = " .. aaa)

            self.text.chars:set(i, c)
        end
    end
end

------------------------------------------------------------------
local function trscSetChar(trsc, c)
    local translate = trsc:get('translate')
    local rotation  = trsc:get('rotation')
    local scale     = trsc:get('scale')
    local color     = trsc:get('color')
    c.position = Amaz.Vector3f(translate:get(0), translate:get(1), 0.0) + c.position
    c.rotate   = Amaz.Vector3f(0.0, 0.0, rotation) + c.rotate
    c.scale    = Amaz.Vector3f(scale:get(0) * c.scale.x, scale:get(1) * c.scale.y, c.scale.z)
    c.color    = Amaz.Vector4f(color:get(0), color:get(1), color:get(2), color:get(3))
    return c
end


function TextAnim:trsc()
    while self.text.chars:size() ~= 0 do
        local trsc = self.properties:get("custom_rules"):get('trsc')
        if trsc==nil then break end

        local desc_begin = trsc:get('desc_begin')
        local desc_loop = trsc:get('desc_loop')
        local desc_end = trsc:get('desc_end')

        local begin_i = 0
        local j = 0
        local n = desc_begin:size()
        while (begin_i < self.text.chars:size() and j < n) do
            local c = self.text.chars:get(begin_i)
            if c.utf8code ~= '\n' then
                local trsc = desc_begin:get(j)
                if not trsc:empty() then
                    self.text.chars:set(begin_i, trscSetChar(trsc, c))
                end
                j = j + 1
            end
            begin_i = begin_i + 1
        end

        local end_i = self.text.chars:size() - 1
        j = 0
        n = desc_end:size()
        while (end_i >= begin_i and j < n) do
            local c = self.text.chars:get(end_i)
            if c.utf8code ~= '\n' then
                local trsc = desc_end:get(j)
                if not trsc:empty() then
                    self.text.chars:set(end_i, trscSetChar(trsc, c))
                end
                j = j + 1
            end
            end_i = end_i - 1
        end

        j = 0
        n = desc_loop:size()
        while (begin_i <= end_i and j < n) do
            local c = self.text.chars:get(begin_i)
            if c.utf8code ~= '\n' then
                local trsc = desc_loop:get(j)
                if not trsc:empty() then
                    self.text.chars:set(begin_i, trscSetChar(trsc, c))
                end
                j = j + 1
            end
            begin_i = begin_i + 1
            if j == n then 
                j = 0
            end
        end
        break
    end
end

exports.TextAnim = TextAnim
return exports
