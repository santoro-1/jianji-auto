InfoSticker = {materials = {{id = 0,type = materialType.image,source = "4fe5d049c04845e4b52fa7db863380b4/4fe5d049c04845e4b52fa7db863380b4.png"}},entity,}
    function InfoSticker:new()
        local o = {}
        setmetatable(o, self)
        self.__index = self
        local viewer = director:getViewer()
        local width = viewer:getWidth()
        local scale = width / 720.0 * 1
        o.entity = scene:createEntity("infoSticker" .. math.random())
        o.entity:getTransform():setScale(scale)
        o.entity:addSpriteComponent():getSprite():setTexture(director:getTextureById(0))
        local controller = o.entity:addAnimatorComponent():getController()
        controller:setFps(16)
        local curve = EffectSdk.Line2D.create(EffectSdk.Vec2(0, 0), 5)
        EffectSdk.AnimationFactory.createScaleAnimation(controller, "easeInAnimation", curve, 0.2, false, 1.0)
        local curve = EffectSdk.Line2D.create(EffectSdk.Vec2(0, 1), -5)
        EffectSdk.AnimationFactory.createScaleAnimation(controller, "easeOutAnimation", curve, 0.2, false, 1.0)
        return o
    end
