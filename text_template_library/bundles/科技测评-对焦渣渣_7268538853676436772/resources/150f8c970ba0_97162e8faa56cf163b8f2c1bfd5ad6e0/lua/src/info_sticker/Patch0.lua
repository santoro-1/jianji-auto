
--- Detect user configuration changes
local Patch0 = {}
Patch0.__index = Patch0


function Patch0.new (env, compNew, compOld)
    local self = setmetatable({}, Patch0)
    self.compNew = compNew
    self.compOld = compOld
    self.compOld:forceTypeSetting()
    self:_cacheInitialPosition()
    return self
end


function Patch0:isDirty (env)
    self.compOld:forceTypeSetting()
    if self:_checkInitialPosition() then
        self:_cacheInitialPosition()
        return true
    end
    return false
end

function Patch0:_cacheInitialPosition ()
    self._initialPosition = {}
    local cache = {}
    local chars = self.compOld.chars
    for i = 0, chars:size() - 1 do
        local char = chars:get(i)
        table.insert(cache, char.initialPosition:copy())
    end
    self.cache = cache
end

function Patch0:_checkInitialPosition ()
    local cache = self.cache
    local chars = self.compOld.chars
    if chars:size() ~= #cache then
        return true
    end
    for i = 0, chars:size() - 1 do
        local char = chars:get(i)
        local p0 = char.initialPosition
        local p1 = cache[i + 1]
        if p0.x ~= p1.x or p0.y ~= p1.y or p0.z ~= p1.z then
            return true
        end
    end
    return false
end


return Patch0