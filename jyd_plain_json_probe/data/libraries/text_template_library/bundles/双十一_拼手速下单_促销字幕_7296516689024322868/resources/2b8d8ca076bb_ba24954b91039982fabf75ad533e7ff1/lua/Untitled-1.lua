

local parent = {}

function parent:new(name)
    return setmetatable({ name = name}, { __index = parent })
end

function parent:show()
    print(self.name .. ": show in parent:")
end

function parent:hello(arg)
        print(self.name .. ": hello in parent:" .. tostring(arg))
end

function parent:init()
    self.test = 1
end
return  parent



local child = {}


function child:new()
        local obj = parent:new("the child")
        local super_mt = getmetatable(obj)
        -- 当方法在子类中查询不到时，再去父类中去查找。
        setmetatable(_M, super_mt)
        -- 这样设置后，可以通过self.super.method(self, ...) 调用父类的已被覆盖的方法。
        obj.super = setmetatable({}, super_mt)
    return setmetatable(obj, { __index = _M })
end


-- 覆盖父类的方法。
function child:hello()
    self.super:init()
    print(self.test)
end

return child
